import os

from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from models.models import PrintModel
from .serializers import ValidationRequestSerializer
from .services import SUPPORTED_FORMATS, validate_model_file


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def validate_upload(request):
    request_serializer = ValidationRequestSerializer(data=request.data)
    request_serializer.is_valid(raise_exception=True)
    file = request_serializer.validated_data["file"]
    extension = os.path.splitext(file.name)[1].lower()
    result = validate_model_file(file, extension)

    http_status = status.HTTP_200_OK if result["valid"] else status.HTTP_400_BAD_REQUEST
    return Response({
        "valid": result["valid"],
        "format": SUPPORTED_FORMATS.get(extension, "").value if extension in SUPPORTED_FORMATS else None,
        "dimensions": list(result["dimensions"]) if result["dimensions"] else None,
        "errors": result["errors"],
    }, status=http_status)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def validate_saved_model(request, pk):
    model = PrintModel.objects.filter(pk=pk, owner=request.user).first()
    if model is None:
        return Response({"detail": "Модель не найдена."}, status=status.HTTP_404_NOT_FOUND)

    model.status = PrintModel.Status.VALIDATING
    model.save(update_fields=("status", "updated_at"))

    extension = f".{model.format}"
    model.file.open("rb")
    result = validate_model_file(model.file, extension)

    if result["valid"]:
        model.status = PrintModel.Status.VALIDATED
        model.validation_errors = []
        if result["dimensions"]:
            model.width_mm, model.height_mm, model.depth_mm = result["dimensions"]
    else:
        model.status = PrintModel.Status.REJECTED
        model.validation_errors = result["errors"]
    model.save(update_fields=(
        "status",
        "validation_errors",
        "width_mm",
        "height_mm",
        "depth_mm",
        "updated_at",
    ))

    return Response({
        "valid": result["valid"],
        "status": model.status,
        "dimensions": list(result["dimensions"]) if result["dimensions"] else None,
        "errors": result["errors"],
    }, status=status.HTTP_200_OK)
