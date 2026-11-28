from django.contrib import admin
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

from .health import HealthCheckView


urlpatterns = [
    path('admin/', admin.site.urls),
    re_path(r'^health/?$', HealthCheckView.as_view(), name='health-check'),
    re_path(r'^api/schema/?$', SpectacularAPIView.as_view(), name='schema'),
    re_path(r'^api/docs/?$', SpectacularSwaggerView.as_view(url_name='schema'), name='docs'),
    re_path(r'^api/redoc/?$', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/auth/', include('users.auth_urls')),
    path('api/models/', include('models_app.urls')),
    path('api/validation/', include('validation.urls')),
    path('api/integration/', include('integrations.urls')),
    path('api/catalog/', include('catalog.urls')),
    path('api/', include('catalog.equipment_urls')),
    path('api/', include('scheduling.urls')),
    path('api/', include('orders.urls')),
    path('api/', include('notifications.urls')),
    path('', RedirectView.as_view(url='/api/catalog/', permanent=False)),
]
