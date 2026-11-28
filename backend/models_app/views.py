from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import ModelVersion, PrintModel
from .serializers import (
    ModelVersionSerializer,
    ModelVersionUploadSerializer,
    PrintModelSerializer,
)


def _is_staff_role(user) -> bool:
    return (
        getattr(user, "role", "").upper() in {"MANAGER", "ADMIN"}
        or user.is_staff
        or user.is_superuser
    )


class PrintModelListCreateView(generics.ListCreateAPIView):
    serializer_class = PrintModelSerializer

    def get_queryset(self):
        return PrintModel.objects.filter(owner=self.request.user)


class PrintModelDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = PrintModelSerializer

    def get_queryset(self):
        return PrintModel.objects.filter(owner=self.request.user)


class PrintModelVersionListCreateView(generics.ListCreateAPIView):
    serializer_class = ModelVersionSerializer

    def _get_model(self):
        qs = PrintModel.objects.filter(pk=self.kwargs["pk"])
        if not _is_staff_role(self.request.user):
            qs = qs.filter(owner_id=self.request.user.pk)
        return qs.first()

    def get_queryset(self):
        model = self._get_model()
        if model is None:
            return ModelVersion.objects.none()
        return model.versions.prefetch_related("validation_results").all()

    def create(self, request, *args, **kwargs):
        model = PrintModel.objects.filter(
            pk=self.kwargs["pk"],
            owner_id=request.user.pk,
        ).first()
        if model is None:
            return Response({"detail": "Модель не найдена."}, status=status.HTTP_404_NOT_FOUND)
        serializer = ModelVersionUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        version = serializer.create_for_model(model, request.user.pk)
        return Response(
            ModelVersionSerializer(version).data,
            status=status.HTTP_201_CREATED,
        )


@extend_schema(responses={(200, "application/octet-stream"): bytes})
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def download_model(request, pk):
    qs = PrintModel.objects.filter(pk=pk)
    if not _is_staff_role(request.user):
        qs = qs.filter(owner_id=request.user.pk)
    model = qs.first()
    if model is None:
        return Response({"detail": "Модель не найдена."}, status=404)
    model.file.open("rb")
    response = FileResponse(model.file, as_attachment=True, filename=model.original_name)
    response["Content-Length"] = model.size
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@extend_schema(responses={(200, "application/octet-stream"): bytes})
@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def download_model_version(request, pk, version: int):
    qs = PrintModel.objects.filter(pk=pk)
    if not _is_staff_role(request.user):
        qs = qs.filter(owner_id=request.user.pk)
    model = qs.first()
    if model is None:
        return Response({"detail": "Модель не найдена."}, status=404)
    version_obj = model.versions.filter(version=version).first()
    if version_obj is None:
        return Response({"detail": "Версия модели не найдена."}, status=404)
    version_obj.file.open("rb")
    response = FileResponse(
        version_obj.file,
        as_attachment=True,
        filename=version_obj.file_name,
    )
    response["Content-Length"] = version_obj.size_bytes
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
