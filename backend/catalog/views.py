from rest_framework import viewsets
from .models import (
    Workshop, Technology, QualityProfile,
    Material, Color, Printer
)
from .serializers import (
    WorkshopSerializer, TechnologySerializer, QualityProfileSerializer,
    MaterialSerializer, ColorSerializer, PrinterSerializer
)
from .permissions import IsAdminOrReadOnly


class WorkshopViewSet(viewsets.ModelViewSet):
    queryset = Workshop.objects.all()
    serializer_class = WorkshopSerializer
    permission_classes = [IsAdminOrReadOnly]


class TechnologyViewSet(viewsets.ModelViewSet):
    queryset = Technology.objects.all()
    serializer_class = TechnologySerializer
    permission_classes = [IsAdminOrReadOnly]


class QualityProfileViewSet(viewsets.ModelViewSet):
    queryset = QualityProfile.objects.all()
    serializer_class = QualityProfileSerializer
    permission_classes = [IsAdminOrReadOnly]


class MaterialViewSet(viewsets.ModelViewSet):
    queryset = Material.objects.select_related('technology').all()
    serializer_class = MaterialSerializer
    permission_classes = [IsAdminOrReadOnly]


class ColorViewSet(viewsets.ModelViewSet):
    queryset = Color.objects.all()
    serializer_class = ColorSerializer
    permission_classes = [IsAdminOrReadOnly]


class PrinterViewSet(viewsets.ModelViewSet):
    queryset = Printer.objects.select_related('workshop', 'technology').all()
    serializer_class = PrinterSerializer
    permission_classes = [IsAdminOrReadOnly]
