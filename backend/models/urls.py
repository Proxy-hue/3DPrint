from django.urls import path

from .views import PrintModelDetailView, PrintModelListCreateView, download_model


urlpatterns = [
    path("", PrintModelListCreateView.as_view(), name="model-list-create"),
    path("<int:pk>/", PrintModelDetailView.as_view(), name="model-detail"),
    path("<int:pk>/download/", download_model, name="model-download"),
]
