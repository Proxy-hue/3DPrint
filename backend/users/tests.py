from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class UserModuleTests(APITestCase):
    def test_registers_client(self):
        response = self.client.post(
            reverse("user-register"),
            {
                "username": "client1",
                "email": "client1@example.com",
                "first_name": "Иван",
                "last_name": "Иванов",
                "phone": "+7 900 000-00-00",
                "password": "Strong-pass-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="client1")
        self.assertEqual(user.role, User.Role.CLIENT)
        self.assertTrue(user.check_password("Strong-pass-123"))

    def test_profile_requires_authentication(self):
        response = self.client.get(reverse("user-profile"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_and_profile(self):
        user = User.objects.create_user(
            username="client2",
            email="client2@example.com",
            password="Strong-pass-123",
            role=User.Role.CLIENT,
        )

        login = self.client.post(
            reverse("user-login"),
            {"username": "client2", "password": "Strong-pass-123"},
            format="json",
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        profile = self.client.get(reverse("user-profile"))
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertEqual(profile.data["id"], user.id)
        self.assertEqual(profile.data["role"], User.Role.CLIENT)
