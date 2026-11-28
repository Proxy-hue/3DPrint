from django.urls import path

from .views import (
    OrderDetailView,
    OrderListCreateView,
    PrintModelDetailView,
    PrintModelListCreateView,
    PrintModelVersionListCreateView,
    calculate_price,
    download_model,
    download_model_version,
    materials,
)


urlpatterns = [
    path("", PrintModelListCreateView.as_view(), name="model-list-create"),
    path("materials/", materials, name="model-materials"),
    path("calculate-price/", calculate_price, name="model-calculate-price"),
    path("orders/", OrderListCreateView.as_view(), name="order-list-create"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order-detail"),
    path("<int:pk>/", PrintModelDetailView.as_view(), name="model-detail"),
    path("<int:pk>/download/", download_model, name="model-download"),
    path(
        "<int:pk>/versions/",
        PrintModelVersionListCreateView.as_view(),
        name="model-version-list-create",
    ),
    path(
        "<int:pk>/versions/<int:version>/file/",
        download_model_version,
        name="model-version-download",
    ),
]
