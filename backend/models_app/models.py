import os
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.db.models import Q

from common.models import BaseModel


def model_upload_path(instance, filename):
    extension = os.path.splitext(filename)[1].lower()
    if extension not in {".stl", ".obj", ".3mf"}:
        extension = ".bin"
    return f"models/{uuid4().hex}{extension}"


class PrintModel(BaseModel):
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
    draft_id = models.CharField(max_length=128, blank=True, default="")
    original_name = models.CharField(max_length=255)
    format = models.CharField(max_length=5, choices=Format.choices)
    size = models.PositiveBigIntegerField()
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPLOADED,
    )
    validation_errors = models.JSONField(default=list, blank=True)
    validation_result = models.JSONField(default=dict, blank=True)
    width_mm = models.FloatField(null=True, blank=True)
    height_mm = models.FloatField(null=True, blank=True)
    depth_mm = models.FloatField(null=True, blank=True)
    volume_cm3 = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "print_model"
        ordering = ("-created_at",)
        verbose_name = "3D-модель"
        verbose_name_plural = "3D-модели"

    def __str__(self):
        return self.original_name


class ModelVersion(BaseModel):
    print_model = models.ForeignKey(
        PrintModel,
        on_delete=models.CASCADE,
        related_name="versions",
        verbose_name="модель",
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="model_versions",
        verbose_name="заказ",
    )
    version = models.PositiveIntegerField("версия")
    file = models.FileField(upload_to=model_upload_path)
    file_name = models.CharField("имя файла", max_length=255)
    format = models.CharField("формат", max_length=5, choices=PrintModel.Format.choices)
    size_bytes = models.PositiveBigIntegerField("размер, байт")
    storage_key = models.CharField("ключ в хранилище", max_length=512)
    bbox_x = models.FloatField("габарит X, мм", null=True, blank=True)
    bbox_y = models.FloatField("габарит Y, мм", null=True, blank=True)
    bbox_z = models.FloatField("габарит Z, мм", null=True, blank=True)
    volume_cm3 = models.FloatField("объём, см³", null=True, blank=True)
    is_current = models.BooleanField("текущая версия", default=True)

    class Meta:
        db_table = "model_version"
        ordering = ("-version", "-created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("print_model", "version"),
                name="uniq_model_version_number",
            ),
            models.UniqueConstraint(
                fields=("print_model",),
                condition=Q(is_current=True),
                name="uniq_current_model_version",
            ),
        ]
        verbose_name = "версия 3D-модели"
        verbose_name_plural = "версии 3D-моделей"

    def __str__(self):
        return f"{self.file_name} (v{self.version})"


class ValidationResultRecord(BaseModel):
    class Verdict(models.TextChoices):
        OK = "OK", "OK"
        WARNING = "WARNING", "WARNING"
        ERROR = "ERROR", "ERROR"

    model_version = models.ForeignKey(
        ModelVersion,
        on_delete=models.CASCADE,
        related_name="validation_results",
        verbose_name="версия модели",
    )
    verdict = models.CharField("вердикт", max_length=16, choices=Verdict.choices)
    issues = models.JSONField("замечания и ошибки", default=list, blank=True)
    needs_support = models.BooleanField("требуются поддержки", default=False)

    class Meta:
        db_table = "validation_result"
        ordering = ("-created_at",)
        verbose_name = "результат проверки модели"
        verbose_name_plural = "результаты проверки моделей"

    def __str__(self):
        return f"{self.model_version} — {self.verdict}"
