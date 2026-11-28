from django.urls import path

from .views import LoadView


urlpatterns = [
    path('load/', LoadView.as_view()),
]
