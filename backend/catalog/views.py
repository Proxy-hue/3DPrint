from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import (
    ADMIN, MANAGER, IsAnyRole, IsManagerOrAdmin, get_role,
)

from . import services
from .models import (
    Color, DeliveryMethod, Material, PickupPoint, PostProcessing, Printer,
    QualityProfile, Technology, Workshop,
)
from .serializers import (
    ColorSerializer, CompatibilitySerializer, DeliveryMethodSerializer,
    MaterialDetailSerializer, MaterialPublicSerializer,
    PickupPointSerializer, PostProcessingSerializer, PrinterSerializer,
    QualityProfileDetailSerializer, QualityProfilePublicSerializer,
    TechnologyDetailSerializer, TechnologyPublicSerializer,
    WorkshopSerializer,
)


class CatalogReadViewSet(viewsets.ReadOnlyModelViewSet):
    """Чтение справочника: К, М, А. Клиент не видит тарифные поля."""

    permission_classes = [IsAnyRole]
    public_serializer_class = None
    detail_serializer_class = None

    def get_serializer_class(self):
        user = getattr(getattr(self, 'request', None), 'user', None)
        if (self.detail_serializer_class
                and get_role(user) in (MANAGER, ADMIN)):
            return self.detail_serializer_class
        return self.public_serializer_class


class TechnologyViewSet(CatalogReadViewSet):
    queryset = Technology.objects.filter(is_active=True)
    public_serializer_class = TechnologyPublicSerializer
    detail_serializer_class = TechnologyDetailSerializer


class QualityProfileViewSet(CatalogReadViewSet):
    queryset = QualityProfile.objects.filter(is_active=True)
    public_serializer_class = QualityProfilePublicSerializer
    detail_serializer_class = QualityProfileDetailSerializer


class MaterialViewSet(CatalogReadViewSet):
    queryset = Material.objects.filter(is_active=True).prefetch_related(
        'technologies', 'colors'
    )
    public_serializer_class = MaterialPublicSerializer
    detail_serializer_class = MaterialDetailSerializer


class ColorViewSet(CatalogReadViewSet):
    queryset = Color.objects.filter(is_active=True)
    public_serializer_class = ColorSerializer


class PostProcessingViewSet(CatalogReadViewSet):
    queryset = PostProcessing.objects.filter(is_active=True)
    public_serializer_class = PostProcessingSerializer


class DeliveryMethodViewSet(CatalogReadViewSet):
    queryset = DeliveryMethod.objects.filter(is_active=True)
    public_serializer_class = DeliveryMethodSerializer


class PickupPointViewSet(CatalogReadViewSet):
    queryset = PickupPoint.objects.filter(is_active=True)
    public_serializer_class = PickupPointSerializer


class CompatibilityView(APIView):
    """Правила совместимости параметров (F-CLI-03)."""

    permission_classes = [IsAnyRole]

    @extend_schema(responses=CompatibilitySerializer)
    def get(self, request):
        data = services.build_compatibility_matrix()
        return Response(CompatibilitySerializer(data).data)


class WorkshopViewSet(viewsets.ReadOnlyModelViewSet):
    """Цеха: М, А. Изменение — только в Django admin."""

    permission_classes = [IsManagerOrAdmin]
    queryset = Workshop.objects.all()
    serializer_class = WorkshopSerializer


class PrinterViewSet(viewsets.ReadOnlyModelViewSet):
    """Принтеры: М, А. Изменение — только в Django admin."""

    permission_classes = [IsManagerOrAdmin]
    queryset = Printer.objects.select_related(
        'workshop', 'technology'
    ).prefetch_related('materials')
    serializer_class = PrinterSerializer
