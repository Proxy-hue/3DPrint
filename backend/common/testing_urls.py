"""URLconf для тестов: не зависит от состояния config/urls.py."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/catalog/', include('catalog.urls')),
    path('api/', include('catalog.equipment_urls')),
    path('api/', include('scheduling.urls')),
]
