from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from .models import PrintModel


class PrintModelTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="model-client",
            email="model-client@example.com",
            password="Strong-pass-123",
        )
        self.client.force_authenticate(self.user)

    def test_upload_stl_model(self):
        file = SimpleUploadedFile(
            "part.stl",
            (
                b"solid part\n"
                b"facet normal 0 0 1\n"
                b"outer loop\n"
                b"vertex 0 0 0\n"
                b"vertex 10 0 0\n"
                b"vertex 0 20 30\n"
                b"endloop\n"
                b"endfacet\n"
                b"endsolid part\n"
            ),
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

    def test_rejects_unsupported_format(self):
        file = SimpleUploadedFile("part.step", b"STEP data", content_type="application/step")
        response = self.client.post(
            reverse("model-list-create"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_file_over_50_mb(self):
        file = SimpleUploadedFile(
            "large.obj",
            b"x" * (50 * 1024 * 1024 + 1),
            content_type="text/plain",
        )
        response = self.client.post(
            reverse("model-list-create"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_cannot_read_another_users_model(self):
        other = User.objects.create_user(
            username="other-client",
            email="other@example.com",
            password="Strong-pass-123",
        )
        model = PrintModel.objects.create(
            owner=other,
            file="models/other/part.stl",
            original_name="part.stl",
            format=PrintModel.Format.STL,
            size=20,
        )

        response = self.client.get(reverse("model-detail", args=[model.pk]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
