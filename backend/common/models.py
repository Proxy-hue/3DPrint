import uuid

from django.db import models


class BaseModel(models.Model):
    """Базовая модель: UUID-ключ и временные метки (спецификация 5.3.3).

    Абстрактная модель, поэтому приложение ``common`` не нужно добавлять
    в INSTALLED_APPS и миграции для него не создаются.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
