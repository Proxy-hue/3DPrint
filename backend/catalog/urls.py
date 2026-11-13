from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    WorkshopViewSet, TechnologyViewSet, QualityProfileViewSet,
    MaterialViewSet, ColorViewSet, PrinterViewSet
)


router = DefaultRouter()
router.register(r'workshops', WorkshopViewSet)
router.register(r'technologies', TechnologyViewSet)
router.register(r'quality-profiles', QualityProfileViewSet)
router.register(r'materials', MaterialViewSet)
router.register(r'colors', ColorViewSet)
router.register(r'printers', PrinterViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
