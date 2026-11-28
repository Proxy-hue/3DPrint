import re
from pathlib import Path
from unittest.mock import patch

import trimesh
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework import status
from rest_framework.test import APITransactionTestCase

from models_app.api import upload_model
from models_app.contracts import ModelUploadCommand
from users.models import User
from validation.api import ValidationContext

from .models import ModelVersion, PrintModel, ValidationResultRecord


class PrintModelTests(APITransactionTestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="model-client@example.com",
            password="Strong-pass-123",
        )
        self.client.force_authenticate(self.user)
        self.queue = self.enterContext(patch("models_app.api.django_rq.get_queue"))
        self.queue.return_value.enqueue.side_effect = (
            lambda task, *args, **kwargs: task(*args, **kwargs)
        )

    def tearDown(self):
        for model in PrintModel.objects.all():
            if re.fullmatch(r"models/[0-9a-f]{32}\.(stl|obj|3mf)", model.file.name):
                model.file.delete(save=False)
        super().tearDown()

    def test_upload_stl_model(self):
        file = SimpleUploadedFile(
            "part.stl",
            trimesh.creation.box(extents=(10, 20, 30)).export(file_type="stl"),
            content_type="model/stl",
        )
        response = self.client.post(
            reverse("model-list-create"),
            {"file": file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        model = PrintModel.objects.get(owner=self.user)
        self.assertEqual(model.format, PrintModel.Format.STL)
        self.assertEqual(model.status, PrintModel.Status.VALIDATED)
        self.assertEqual(model.original_name, "part.stl")
        self.assertRegex(model.file.name, r"^models/[0-9a-f]{32}\.stl$")
        self.assertEqual(model.validation_result["state"], "completed")
        self.assertNotIn(
            Path(settings.MEDIA_ROOT) / model.file.name,
            Path(model.file.path).parents,
        )
        self.queue.return_value.enqueue.assert_called_once()

    def test_bad_model_is_saved_with_validation_error(self):
        file = SimpleUploadedFile("broken.obj", b"not an OBJ", content_type="text/plain")
        response = self.client.post(
            reverse("model-list-create"),
            {"file": file},
            format="multipart",
        )

        model = PrintModel.objects.get(owner=self.user)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(model.status, PrintModel.Status.REJECTED)
        self.assertEqual(model.validation_result["findings"][0]["code"], "E-02")
        self.assertTrue(model.file.storage.exists(model.file.name))

    def test_upload_passes_known_validation_context_to_worker(self):
        uploaded_file = SimpleUploadedFile(
            "part.obj",
            trimesh.creation.box().export(file_type="obj").encode("utf-8"),
            content_type="text/plain",
        )

        result = upload_model(
            ModelUploadCommand(
                owner_id=self.user.pk,
                draft_id="draft-123",
                filename=uploaded_file.name,
                file=uploaded_file,
                validation_context=ValidationContext(
                    technology="FDM",
                    assembly_selected=True,
                ),
            )
        )

        self.assertIsNotNone(result.model)
        queued_args = self.queue.return_value.enqueue.call_args.args
        self.assertEqual(queued_args[3:], ("FDM", True))

    def test_queue_failure_keeps_stored_model_and_returns_service_error(self):
        self.queue.return_value.enqueue.side_effect = RedisConnectionError("offline")
        file = SimpleUploadedFile(
            "part.obj",
            trimesh.creation.box().export(file_type="obj").encode("utf-8"),
            content_type="text/plain",
        )
        with self.assertLogs("models_app.api", level="ERROR"):
            response = self.client.post(
                reverse("model-list-create"),
                {"file": file},
                format="multipart",
            )

        model = PrintModel.objects.get(owner=self.user)
        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(model.status, PrintModel.Status.UPLOADED)
        self.assertTrue(model.file.storage.exists(model.file.name))
        self.assertEqual(str(response.data["model_id"]), str(model.pk))

    def test_download_is_private_and_available_to_owner_and_manager(self):
        model = PrintModel.objects.create(
            owner=self.user,
            file=SimpleUploadedFile("private.stl", b"private model"),
            original_name="private.stl",
            format=PrintModel.Format.STL,
            size=13,
        )
        download_url = reverse("model-download", args=[model.pk])

        owner_response = self.client.get(download_url)
        self.assertEqual(owner_response.status_code, status.HTTP_200_OK)
        self.assertEqual(owner_response["Content-Disposition"], 'attachment; filename="private.stl"')
        b"".join(owner_response.streaming_content)
        owner_response.close()

        other = User.objects.create_user(
            email="private-other@example.com",
            password="Strong-pass-123",
        )
        self.client.force_authenticate(other)
        self.assertEqual(self.client.get(download_url).status_code, status.HTTP_404_NOT_FOUND)

        manager = User.objects.create_user(
            email="private-manager@example.com",
            password="Strong-pass-123",
            role=User.Role.MANAGER,
        )
        self.client.force_authenticate(manager)
        manager_response = self.client.get(download_url)
        self.assertEqual(manager_response.status_code, status.HTTP_200_OK)
        b"".join(manager_response.streaming_content)
        manager_response.close()

    def test_rejects_unsupported_format(self):
        file = SimpleUploadedFile("part.step", b"STEP data", content_type="application/step")
        response = self.client.post(
            reverse("model-list-create"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("E-01", response.data["file"][0])

    def test_model_versions_and_validation_result_records(self):
        v1_file = SimpleUploadedFile(
            "part_v1.stl",
            trimesh.creation.box(extents=(10, 20, 30)).export(file_type="stl"),
            content_type="model/stl",
        )
        create_resp = self.client.post(
            reverse("model-list-create"),
            {"file": v1_file},
            format="multipart",
        )
        self.assertEqual(create_resp.status_code, status.HTTP_201_CREATED)
        model = PrintModel.objects.get(pk=create_resp.data["id"])
        self.assertEqual(create_resp.data["current_version"], 1)
        self.assertEqual(create_resp.data["verdict"], "OK")
        self.assertAlmostEqual(model.volume_cm3, 6.0, places=2)

        v1 = ModelVersion.objects.get(print_model=model, version=1)
        self.assertTrue(v1.is_current)
        self.assertEqual(v1.storage_key, model.file.name)
        self.assertEqual(ValidationResultRecord.objects.filter(model_version=v1).count(), 1)

        v2_file = SimpleUploadedFile(
            "part_v2.obj",
            trimesh.creation.box(extents=(20, 20, 20)).export(file_type="obj").encode("utf-8"),
            content_type="text/plain",
        )
        v2_resp = self.client.post(
            reverse("model-version-list-create", args=[model.pk]),
            {"file": v2_file},
            format="multipart",
        )
        self.assertEqual(v2_resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(v2_resp.data["version"], 2)

        v1.refresh_from_db()
        v2 = ModelVersion.objects.get(print_model=model, version=2)
        self.assertFalse(v1.is_current)
        self.assertTrue(v2.is_current)
        self.assertAlmostEqual(v2.volume_cm3, 8.0, places=2)

        v1_download = self.client.get(reverse("model-version-download", args=[model.pk, 1]))
        self.assertEqual(v1_download.status_code, status.HTTP_200_OK)
        b"".join(v1_download.streaming_content)
        v1_download.close()
        v1.file.delete(save=False)

    @override_settings(DEBUG=True, SYNC_VALIDATION_FALLBACK=True)
    def test_sync_validation_fallback_when_redis_unavailable_in_debug(self):
        self.queue.return_value.enqueue.side_effect = RedisConnectionError("offline")
        file = SimpleUploadedFile(
            "fallback.stl",
            trimesh.creation.box(extents=(10, 10, 10)).export(file_type="stl"),
            content_type="model/stl",
        )
        with self.assertLogs("models_app.api", level="WARNING"):
            response = self.client.post(
                reverse("model-list-create"),
                {"file": file},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        model = PrintModel.objects.get(pk=response.data["id"])
        self.assertEqual(model.status, PrintModel.Status.VALIDATED)
        self.assertAlmostEqual(model.volume_cm3, 1.0, places=2)
