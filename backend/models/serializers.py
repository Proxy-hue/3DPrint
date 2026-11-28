from uuid import uuid4

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import APIException

from .api import upload_model, upload_model_version
from .contracts import ModelUploadCommand
from .models import ModelVersion, Order, PrintModel, ValidationResultRecord


class ModelQueueUnavailable(APIException):
    status_code = 503
    default_code = "validation_queue_unavailable"
    default_detail = "Файл сохранён, но фоновая проверка не запущена."


class ValidationResultRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ValidationResultRecord
        fields = ("id", "verdict", "issues", "needs_support", "created_at")


class ModelVersionSerializer(serializers.ModelSerializer):
    latest_validation = serializers.SerializerMethodField()

    class Meta:
        model = ModelVersion
        fields = (
            "id",
            "version",
            "file_name",
            "format",
            "size_bytes",
            "storage_key",
            "bbox_x",
            "bbox_y",
            "bbox_z",
            "volume_cm3",
            "is_current",
            "latest_validation",
            "created_at",
        )

    @extend_schema_field(ValidationResultRecordSerializer(allow_null=True))
    def get_latest_validation(self, obj: ModelVersion):
        record = obj.validation_results.first()
        if record is None:
            return None
        return ValidationResultRecordSerializer(record).data


class PrintModelSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, allow_empty_file=True)
    current_version = serializers.SerializerMethodField()
    verdict = serializers.SerializerMethodField()

    class Meta:
        model = PrintModel
        fields = (
            "id",
            "file",
            "draft_id",
            "original_name",
            "format",
            "size",
            "status",
            "verdict",
            "validation_errors",
            "validation_result",
            "width_mm",
            "height_mm",
            "depth_mm",
            "volume_cm3",
            "current_version",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "draft_id",
            "model",
            "original_name",
            "format",
            "size",
            "status",
            "verdict",
            "validation_errors",
            "validation_result",
            "width_mm",
            "height_mm",
            "depth_mm",
            "volume_cm3",
            "current_version",
            "created_at",
            "updated_at",
        )

    def get_current_version(self, obj: PrintModel) -> int | None:
        current = obj.versions.filter(is_current=True).values_list("version", flat=True).first()
        return current

    def get_verdict(self, obj: PrintModel) -> str | None:
        return obj.validation_result.get("verdict") if isinstance(obj.validation_result, dict) else None

    def create(self, validated_data):
        uploaded_file = validated_data["file"]
        outcome = upload_model(
            ModelUploadCommand(
                owner_id=self.context["request"].user.pk,
                draft_id=uuid4().hex,
                filename=uploaded_file.name,
                file=uploaded_file,
            )
        )
        if outcome.model is None:
            raise serializers.ValidationError(
                {
                    "draft_id": outcome.draft_id,
                    "file": [
                        f"{finding.code}: {finding.message}"
                        for finding in outcome.findings
                    ],
                }
            )
        if outcome.queue_error:
            raise ModelQueueUnavailable(
                {
                    "detail": outcome.queue_error,
                    "model_id": outcome.model.model_id,
                    "draft_id": outcome.draft_id,
                    "status": outcome.model.status,
                }
            )
        return PrintModel.objects.get(pk=outcome.model.model_id)


class ModelVersionUploadSerializer(serializers.Serializer):
    file = serializers.FileField(write_only=True, allow_empty_file=True)

    def create_for_model(self, print_model: PrintModel, user_id: int) -> ModelVersion:
        uploaded_file = self.validated_data["file"]
        outcome = upload_model_version(
            print_model.pk,
            ModelUploadCommand(
                owner_id=user_id,
                draft_id=print_model.draft_id or uuid4().hex,
                filename=uploaded_file.name,
                file=uploaded_file,
            ),
        )
        if outcome is None:
            raise serializers.ValidationError({"detail": "Модель не найдена."})
        if outcome.model is None:
            raise serializers.ValidationError(
                {
                    "draft_id": outcome.draft_id,
                    "file": [
                        f"{finding.code}: {finding.message}"
                        for finding in outcome.findings
                    ],
                }
            )
        if outcome.queue_error:
            raise ModelQueueUnavailable(
                {
                    "detail": outcome.queue_error,
                    "model_id": outcome.model.model_id,
                    "draft_id": outcome.draft_id,
                    "status": outcome.model.status,
                }
            )
        return ModelVersion.objects.get(
            print_model=print_model,
            version=outcome.model.version,
        )


class OrderSerializer(serializers.ModelSerializer):
    model_id = serializers.PrimaryKeyRelatedField(
        source="model",
        queryset=PrintModel.objects.all(),
        write_only=True,
    )
    model = PrintModelSerializer(read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "model_id",
            "model",
            "status",
            "configuration",
            "price",
            "equipment_compatible",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "model",
            "status",
            "price",
            "equipment_compatible",
            "created_at",
            "updated_at",
        )

    def validate_model_id(self, model):
        request = self.context["request"]
        if model.owner_id != request.user.id:
            raise serializers.ValidationError("Модель не принадлежит текущему пользователю.")
        if model.status != PrintModel.Status.VALIDATED:
            raise serializers.ValidationError("Модель должна быть успешно проверена.")
        return model
