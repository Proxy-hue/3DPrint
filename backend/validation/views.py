import os

from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from models_app.api import revalidate_model

from .api import SUPPORTED_FORMATS, validate_file
from .serializers import ValidationRequestSerializer


@extend_schema(request=ValidationRequestSerializer, responses={200: None, 400: None})
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def validate_upload(request):
    request_serializer = ValidationRequestSerializer(data=request.data)
    request_serializer.is_valid(raise_exception=True)
    file = request_serializer.validated_data["file"]
    result = validate_file(file, file.name)

    http_status = status.HTTP_200_OK if result.valid else status.HTTP_400_BAD_REQUEST
    extension = os.path.splitext(file.name)[1].lower()
    return Response(
        {
            "valid": result.valid,
            "verdict": result.verdict,
            "format": SUPPORTED_FORMATS.get(extension),
            "dimensions": list(result.dimensions_mm) if result.dimensions_mm else None,
            "volume_cm3": result.volume_cm3,
            "needs_support": result.needs_support,
            "errors": [finding.message for finding in result.findings],
            "findings": [
                {
                    "code": finding.code,
                    "severity": finding.severity,
                    "message": finding.message,
                }
                for finding in result.findings
            ],
        },
        status=http_status,
    )


@extend_schema(request=None, responses={200: None, 202: None, 404: None, 503: None})
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def validate_saved_model(request, pk):
    result = revalidate_model(pk, owner_id=request.user.id)
    if result is None:
        return Response({"detail": "Модель не найдена."}, status=status.HTTP_404_NOT_FOUND)

    if not result.queued:
        response_status = status.HTTP_503_SERVICE_UNAVAILABLE
    elif result.valid is None:
        response_status = status.HTTP_202_ACCEPTED
    else:
        response_status = status.HTTP_200_OK
    return Response(
        {
            "valid": result.valid,
            "verdict": result.verdict,
            "status": result.status,
            "dimensions": list(result.dimensions_mm) if result.dimensions_mm else None,
            "volume_cm3": result.volume_cm3,
            "errors": list(result.errors),
        },
        status=response_status,
    )
