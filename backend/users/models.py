from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "client", "Клиент"
        MANAGER = "manager", "Менеджер"
        ADMIN = "admin", "Администратор"
        INTEGRATION = "integration", "Интеграционный клиент"

    class ClientType(models.TextChoices):
        INDIVIDUAL = "individual", "Физлицо"
        ORGANIZATION = "organization", "Организация"

    email = models.EmailField("email", unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField("телефон", max_length=20, blank=True)
    client_type = models.CharField(
        "тип клиента",
        max_length=20,
        choices=ClientType.choices,
        default=ClientType.INDIVIDUAL,
    )
    company_name = models.CharField("организация", max_length=255, blank=True, default="")
    consent_at = models.DateTimeField("согласие на обработку ПДн", null=True, blank=True)
    is_senior = models.BooleanField("старший менеджер", default=False)
    updated_at = models.DateTimeField("обновлён", auto_now=True)

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        if self.is_superuser:
            self.role = self.Role.ADMIN
            self.is_staff = True
        elif self.role == self.Role.ADMIN:
            self.is_staff = True
        else:
            self.is_staff = False
        super().save(*args, **kwargs)

    def __str__(self):
        return self.get_full_name() or self.email or self.username
