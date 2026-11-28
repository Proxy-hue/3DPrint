from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ColorViewSet, CompatibilityView, DeliveryMethodViewSet, MaterialViewSet,
    PickupPointViewSet, PostProcessingViewSet, QualityProfileViewSet,
    TechnologyViewSet,
)

router = DefaultRouter()
router.register(r'technologies', TechnologyViewSet)
router.register(r'quality-profiles', QualityProfileViewSet)
router.register(r'materials', MaterialViewSet)
router.register(r'colors', ColorViewSet)
router.register(r'post-processing', PostProcessingViewSet)
router.register(r'delivery-methods', DeliveryMethodViewSet)
router.register(r'pickup-points', PickupPointViewSet)


urlpatterns = [
    path('compatibility/', CompatibilityView.as_view()),
    path('', include(router.urls)),
]
