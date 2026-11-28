import uuid

from django.contrib.auth.models import (
    AbstractUser,
    Group,
    Permission,
    UserManager as BaseUserManager,
)
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Пользователь должен иметь email")
        email = self.normalize_email(email).strip().lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("role", User.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "CLIENT", "Клиент"
        MANAGER = "MANAGER", "Менеджер"
        ADMIN = "ADMIN", "Администратор"
        INTEGRATION = "INTEGRATION", "Интеграционный клиент"

    class ClientType(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Физлицо"
        ORGANIZATION = "ORGANIZATION", "Организация"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField("телефон", max_length=20, blank=True)
    client_type = models.CharField(
        "тип клиента",
        max_length=20,
        choices=ClientType.choices,
        default=ClientType.INDIVIDUAL,
    )
    company_name = models.CharField("организация", max_length=255, blank=True)
    consent_at = models.DateTimeField("согласие на обработку ПДн", null=True, blank=True)
    is_senior = models.BooleanField("старший менеджер", default=False)
    updated_at = models.DateTimeField("обновлён", auto_now=True)

    groups = models.ManyToManyField(
        Group,
        verbose_name="groups",
        blank=True,
        help_text="The groups this user belongs to.",
        related_name="custom_user_groups",
        related_query_name="custom_user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name="user permissions",
        blank=True,
        help_text="Specific permissions for this user.",
        related_name="custom_user_permissions",
        related_query_name="custom_user",
    )

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        normalized_role = (self.role or self.Role.CLIENT).upper()
        self.role = normalized_role
        if self.is_superuser:
            self.role = self.Role.ADMIN
            self.is_staff = True
        elif self.role == self.Role.ADMIN:
            self.is_staff = True
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
