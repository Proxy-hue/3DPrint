from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = "client", "Клиент"
        MANAGER = "manager", "Менеджер"
        ADMIN = "admin", "Администратор"
        INTEGRATION = "integration", "Интеграционный клиент"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    phone = models.CharField("телефон", max_length=20, blank=True)

    def __str__(self):
        return self.get_full_name() or self.username
