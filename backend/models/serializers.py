import os

from rest_framework import serializers

from .models import PrintModel
from validation.services import SUPPORTED_FORMATS, validate_model_file


class PrintModelSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = PrintModel
        fields = (
            "id",
            "file",
            "original_name",
            "format",
            "size",
            "status",
            "validation_errors",
            "width_mm",
            "height_mm",
            "depth_mm",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "original_name",
            "format",
            "size",
            "status",
            "validation_errors",
            "width_mm",
            "height_mm",
            "depth_mm",
            "created_at",
            "updated_at",
        )

    def validate_file(self, file):
        extension = os.path.splitext(file.name)[1].lower()
        if extension not in SUPPORTED_FORMATS:
            raise serializers.ValidationError("Поддерживаются только STL, OBJ и 3MF.")

        result = validate_model_file(file, extension)
        if not result["valid"]:
            raise serializers.ValidationError(result["errors"])
        return file

    def create(self, validated_data):
        file = validated_data["file"]
        extension = os.path.splitext(file.name)[1].lower()
        return PrintModel.objects.create(
            owner=self.context["request"].user,
            file=file,
            original_name=os.path.basename(file.name),
            format=SUPPORTED_FORMATS[extension],
            size=file.size,
            status=PrintModel.Status.VALIDATED,
        )
