from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User
from models.models import PrintModel


class ValidationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="validator",
            email="validator@example.com",
            password="Strong-pass-123",
        )
        self.client.force_authenticate(self.user)

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
        file = SimpleUploadedFile(
            "cube.obj",
            b"v 0 0 0\nv 10 20 30\n",
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
            file=SimpleUploadedFile("cube.obj", b"v 0 0 0\nv 5 6 7\n"),
            original_name="cube.obj",
            format=PrintModel.Format.OBJ,
            size=20,
        )
        response = self.client.post(reverse("validation-model", args=[model.pk]))

        model.refresh_from_db()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(model.status, PrintModel.Status.VALIDATED)
        self.assertEqual(model.width_mm, 5.0)
