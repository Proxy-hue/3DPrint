import re
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
import trimesh
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from models.models import PrintModel
from validation.api import validate_file
from validation.contracts import ValidationContext
from validation.services import (
    MAX_3MF_UNCOMPRESSED_SIZE,
    MAX_FILE_SIZE,
    _validate_3mf_archive,
)


def export_mesh(mesh: trimesh.Trimesh, file_type: str) -> bytes:
    data = mesh.export(file_type=file_type)
    return data.encode("utf-8") if isinstance(data, str) else data


def box_mesh(
    extents: tuple[float, float, float] = (10.0, 20.0, 30.0),
) -> trimesh.Trimesh:
    return trimesh.creation.box(extents=extents)


def meter_3mf() -> bytes:
    model_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<model unit="meter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">
  <resources>
    <object id="1" type="model">
      <mesh>
        <vertices>
          <vertex x="0" y="0" z="0"/>
          <vertex x="0.01" y="0" z="0"/>
          <vertex x="0" y="0.01" z="0"/>
          <vertex x="0" y="0" z="0.01"/>
        </vertices>
        <triangles>
          <triangle v1="0" v2="2" v3="1"/>
          <triangle v1="0" v2="1" v3="3"/>
          <triangle v1="0" v2="3" v3="2"/>
          <triangle v1="1" v2="2" v3="3"/>
        </triangles>
      </mesh>
    </object>
  </resources>
  <build><item objectid="1"/></build>
</model>
"""
    archive = BytesIO()
    with ZipFile(archive, "w", ZIP_DEFLATED) as zip_file:
        zip_file.writestr("3D/3dmodel.model", model_xml)
    return archive.getvalue()


class ValidationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="validator",
            email="validator@example.com",
            password="Strong-pass-123",
        )
        self.client.force_authenticate(self.user)
        queue_patcher = patch("models.api.django_rq.get_queue")
        self.addCleanup(queue_patcher.stop)
        self.queue = queue_patcher.start()
        self.queue.return_value.enqueue.side_effect = (
            lambda task, *args, **kwargs: task(*args, **kwargs)
        )

    def tearDown(self):
        for model in PrintModel.objects.all():
            if re.fullmatch(r"models/[0-9a-f]{32}\.(stl|obj|3mf)", model.file.name):
                model.file.delete(save=False)
        super().tearDown()

    def test_rejects_empty_file(self):
        file = SimpleUploadedFile("empty.stl", b"", content_type="model/stl")
        response = self.client.post(
            reverse("validation-upload"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(response.data["errors"])

    def test_validates_obj_dimensions(self):
        obj = export_mesh(box_mesh(), "obj")
        file = SimpleUploadedFile(
            "cube.obj",
            obj,
            content_type="text/plain",
        )
        response = self.client.post(
            reverse("validation-upload"),
            {"file": file},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["dimensions"], [10.0, 20.0, 30.0])

    def test_revalidates_saved_model(self):
        model = PrintModel.objects.create(
            owner=self.user,
            file=SimpleUploadedFile(
                "cube.obj",
                export_mesh(box_mesh((5.0, 6.0, 7.0)), "obj"),
            ),
            original_name="cube.obj",
            format=PrintModel.Format.OBJ,
            size=20,
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("validation-model", args=[model.pk]))

        model.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIsNone(response.data["valid"])
        self.assertEqual(model.status, PrintModel.Status.VALIDATED)
        self.assertEqual(model.width_mm, 5.0)
        self.assertEqual(model.validation_result["state"], "completed")

    def test_loads_stl_obj_and_3mf_with_dimensions(self):
        mesh = box_mesh()
        for file_type in ("stl", "obj", "3mf"):
            with self.subTest(file_type=file_type):
                result = validate_file(
                    BytesIO(export_mesh(mesh, file_type)),
                    f"box.{file_type}",
                )

                self.assertTrue(result.valid)
                self.assertEqual(result.dimensions_mm, (10.0, 20.0, 30.0))

    def test_converts_3mf_units_to_millimeters(self):
        result = validate_file(BytesIO(meter_3mf()), "meter-model.3mf")

        self.assertTrue(result.valid)
        self.assertEqual(result.dimensions_mm, (10.0, 10.0, 10.0))

    def test_rejects_signature_mismatch_with_e01(self):
        result = validate_file(BytesIO(export_mesh(box_mesh(), "obj")), "model.stl")

        self.assertFalse(result.valid)
        self.assertEqual(result.findings[0].code, "E-01")

    def test_rejects_oversized_upload_with_e01(self):
        class OversizedFile:
            name = "large.stl"
            size = MAX_FILE_SIZE + 1

        result = validate_file(OversizedFile(), "large.stl")

        self.assertFalse(result.valid)
        self.assertEqual(result.findings[0].code, "E-01")

    def test_reports_point_cloud_as_degenerate_e03(self):
        obj = b"v 0 0 0\nv 10 20 30\n"
        result = validate_file(BytesIO(obj), "points.obj")

        self.assertFalse(result.valid)
        self.assertEqual(result.findings[0].code, "E-03")

    def test_attempts_to_repair_open_mesh_in_memory_with_w01(self):
        mesh = box_mesh()
        mesh.update_faces(np.arange(len(mesh.faces)) != 0)
        result = validate_file(BytesIO(export_mesh(mesh, "stl")), "open.stl")

        codes = {finding.code for finding in result.findings}
        self.assertTrue(result.valid)
        self.assertIn("W-01", codes)
        self.assertNotIn("E-03", codes)

    def test_wall_thickness_warning_uses_selected_technology(self):
        file_data = export_mesh(box_mesh((0.6, 10.0, 10.0)), "stl")

        fdm_result = validate_file(
            BytesIO(file_data),
            "thin.stl",
            ValidationContext(technology="FDM"),
        )
        sls_result = validate_file(
            BytesIO(file_data),
            "thin.stl",
            ValidationContext(technology="SLS"),
        )

        self.assertIn("W-02", {finding.code for finding in fdm_result.findings})
        self.assertNotIn("W-02", {finding.code for finding in sls_result.findings})

    def test_overhang_warning_sets_support_result(self):
        mesh = box_mesh()
        mesh.apply_transform(
            trimesh.transformations.rotation_matrix(
                np.deg2rad(30),
                (0, 1, 0),
            )
        )
        result = validate_file(BytesIO(export_mesh(mesh, "stl")), "tilted.stl")

        self.assertIn("W-03", {finding.code for finding in result.findings})
        self.assertTrue(result.needs_support)
        self.assertEqual(result.support_factor, 1.0)

    def test_disconnected_bodies_warn_unless_assembly_selected(self):
        first = box_mesh()
        second = box_mesh()
        second.apply_translation((30, 0, 0))
        data = export_mesh(trimesh.util.concatenate((first, second)), "stl")

        separate_result = validate_file(BytesIO(data), "parts.stl")
        assembly_result = validate_file(
            BytesIO(data),
            "parts.stl",
            ValidationContext(assembly_selected=True),
        )

        self.assertIn("W-04", {finding.code for finding in separate_result.findings})
        self.assertNotIn("W-04", {finding.code for finding in assembly_result.findings})

    def test_warns_about_suspicious_model_units(self):
        result = validate_file(
            BytesIO(export_mesh(box_mesh((1200.0, 20.0, 20.0)), "stl")),
            "large.stl",
        )

        self.assertIn("W-05", {finding.code for finding in result.findings})

    def test_rejects_3mf_over_expansion_limit_with_e02(self):
        archive_context = MagicMock()
        archive_context.__enter__.return_value.infolist.return_value = [
            SimpleNamespace(file_size=MAX_3MF_UNCOMPRESSED_SIZE + 1)
        ]
        with patch("validation.services.zipfile.ZipFile", return_value=archive_context):
            finding = _validate_3mf_archive(b"")

        self.assertIsNotNone(finding)
        self.assertEqual(finding.code, "E-02")
