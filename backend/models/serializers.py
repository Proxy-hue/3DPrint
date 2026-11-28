from uuid import uuid4

from rest_framework import serializers
from rest_framework.exceptions import APIException

from .api import upload_model
from .contracts import ModelUploadCommand
from .models import Order, PrintModel


class ModelQueueUnavailable(APIException):
    status_code = 503
    default_code = "validation_queue_unavailable"
    default_detail = "Файл сохранён, но фоновая проверка не запущена."


class PrintModelSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True, allow_empty_file=True)

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
            "validation_errors",
            "validation_result",
            "width_mm",
            "height_mm",
            "depth_mm",
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
            "validation_errors",
            "validation_result",
            "width_mm",
            "height_mm",
            "depth_mm",
            "created_at",
            "updated_at",
        )

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
                    ]
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
