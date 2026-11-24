from django.urls import path

from .views import validate_saved_model, validate_upload


urlpatterns = [
    path("validate/", validate_upload, name="validation-upload"),
    path("models/<int:pk>/validate/", validate_saved_model, name="validation-model"),
]
