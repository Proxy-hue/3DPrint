from django.conf import settings
from django.db import models


def model_upload_path(instance, filename):
    return f"models/{instance.owner_id}/{filename}"


class PrintModel(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Загружена"
        VALIDATING = "validating", "Проверяется"
        VALIDATED = "validated", "Проверена"
        REJECTED = "rejected", "Отклонена"

    class Format(models.TextChoices):
        STL = "stl", "STL"
        OBJ = "obj", "OBJ"
        THREE_MF = "3mf", "3MF"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="print_models",
    )
    file = models.FileField(upload_to=model_upload_path)
    original_name = models.CharField(max_length=255)
    format = models.CharField(max_length=5, choices=Format.choices)
    size = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    validation_errors = models.JSONField(default=list, blank=True)
    width_mm = models.FloatField(null=True, blank=True)
    height_mm = models.FloatField(null=True, blank=True)
    depth_mm = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.original_name
