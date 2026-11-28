import re

from django.core import mail
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import User


class UserModuleTests(APITestCase):
    def test_auth_register_requires_consent_and_hashes_with_argon2(self):
        rejected = self.client.post(
            reverse("auth-register"),
            {
                "email": "noconsent@example.com",
                "full_name": "Анна Смирнова",
                "password": "Strong-pass-123",
                "consent": False,
            },
            format="json",
        )
        self.assertEqual(rejected.status_code, status.HTTP_400_BAD_REQUEST)

        created = self.client.post(
            reverse("auth-register"),
            {
                "email": "org@example.com",
                "full_name": "ООО Деталь",
                "client_type": User.ClientType.ORGANIZATION,
                "company_name": "ООО Деталь",
                "phone": "+79991112233",
                "password": "Strong-pass-123",
                "consent": True,
            },
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="org@example.com")
        self.assertEqual(user.client_type, User.ClientType.ORGANIZATION)
        self.assertIsNotNone(user.consent_at)
        self.assertFalse(user.is_staff)
        self.assertTrue(user.password.startswith("argon2$"))

    def test_auth_session_login_logout_and_axes_lockout(self):
        User.objects.create_user(
            email="session@example.com",
            password="Strong-pass-123",
            role=User.Role.CLIENT,
        )

        for _ in range(5):
            failed = self.client.post(
                reverse("auth-login"),
                {"email": "session@example.com", "password": "Wrong-password"},
                format="json",
            )
            self.assertEqual(failed.status_code, status.HTTP_401_UNAUTHORIZED)

        locked = self.client.post(
            reverse("auth-login"),
            {"email": "session@example.com", "password": "Strong-pass-123"},
            format="json",
        )
        self.assertEqual(locked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(locked.data["code"], "ACCOUNT_LOCKED")

    def test_auth_session_cookie_csrf_and_logout(self):
        User.objects.create_user(
            email="cookie@example.com",
            password="Strong-pass-123",
            role=User.Role.CLIENT,
        )

        csrf_resp = self.client.get(reverse("auth-csrf"))
        self.assertEqual(csrf_resp.status_code, status.HTTP_200_OK)
        self.assertIn("csrfToken", csrf_resp.data)

        login_resp = self.client.post(
            reverse("auth-login"),
            {"email": "cookie@example.com", "password": "Strong-pass-123"},
            format="json",
        )
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        self.assertIn("csrf_token", login_resp.data)
        self.assertIn("sessionid", login_resp.cookies)
        self.assertTrue(login_resp.cookies["sessionid"]["httponly"])

        me_resp = self.client.get(reverse("auth-me"))
        self.assertEqual(me_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(me_resp.data["email"], "cookie@example.com")

        logout_resp = self.client.post(reverse("auth-logout"))
        self.assertEqual(logout_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get(reverse("auth-me")).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_auth_password_reset_flow(self):
        user = User.objects.create_user(
            email="reset@example.com",
            password="Old-Strong-Password-123",
        )
        req_resp = self.client.post(
            reverse("auth-password-reset"),
            {"email": "reset@example.com"},
            format="json",
        )
        self.assertEqual(req_resp.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        uid = re.search(r"uid:\s*(\S+)", body).group(1)
        token = re.search(r"token:\s*(\S+)", body).group(1)

        confirm_resp = self.client.post(
            reverse("auth-password-reset-confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "New-Strong-Password-456",
            },
            format="json",
        )
        self.assertEqual(confirm_resp.status_code, status.HTTP_200_OK)
        user.refresh_from_db()
        self.assertTrue(user.check_password("New-Strong-Password-456"))

    def test_only_admin_role_has_staff_access(self):
        admin_user = User.objects.create_user(
            email="adm1@example.com",
            password="Strong-pass-123",
            role=User.Role.ADMIN,
        )
        self.assertTrue(admin_user.is_staff)

    def test_health_and_openapi_schema_endpoints(self):
        health = self.client.get(reverse("health-check"))
        self.assertEqual(health.status_code, status.HTTP_200_OK)
        self.assertEqual(health.data["status"], "ok")
        self.assertEqual(health.data["checks"]["database"], "ok")

        schema = self.client.get(reverse("schema"))
        self.assertEqual(schema.status_code, status.HTTP_200_OK)
        self.assertIn("openapi", schema.content.decode("utf-8"))
