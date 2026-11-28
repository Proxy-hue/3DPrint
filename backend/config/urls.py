from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/users/", include("users.urls")),
    path("api/models/", include("models.urls")),
    path("api/validation/", include("validation.urls")),
]
