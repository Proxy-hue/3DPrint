from django.urls import path

from .views import (
    PrintModelDetailView,
    PrintModelListCreateView,
    PrintModelVersionListCreateView,
    download_model,
    download_model_version,
)


urlpatterns = [
    path("", PrintModelListCreateView.as_view(), name="model-list-create"),
    path("<uuid:pk>/", PrintModelDetailView.as_view(), name="model-detail"),
    path("<uuid:pk>/download/", download_model, name="model-download"),
    path(
        "<uuid:pk>/versions/",
        PrintModelVersionListCreateView.as_view(),
        name="model-version-list-create",
    ),
    path(
        "<uuid:pk>/versions/<int:version>/file/",
        download_model_version,
        name="model-version-download",
    ),
]
