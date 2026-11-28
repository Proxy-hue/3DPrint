from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import PrinterViewSet, WorkshopViewSet

router = SimpleRouter()
router.register(r'printers', PrinterViewSet)
router.register(r'workshops', WorkshopViewSet)

# Подключается как path('api/', include('catalog.equipment_urls'))
urlpatterns = [
    path('', include(router.urls)),
]
