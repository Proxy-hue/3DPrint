from django.urls import re_path

from .views import (
    AuthLoginView,
    AuthLogoutView,
    AuthPasswordResetConfirmView,
    AuthPasswordResetView,
    AuthRegisterView,
    ProfileView,
    csrf_view,
)


urlpatterns = [
    re_path(r"^csrf/?$", csrf_view, name="auth-csrf"),
    re_path(r"^register/?$", AuthRegisterView.as_view(), name="auth-register"),
    re_path(r"^login/?$", AuthLoginView.as_view(), name="auth-login"),
    re_path(r"^logout/?$", AuthLogoutView.as_view(), name="auth-logout"),
    re_path(r"^me/?$", ProfileView.as_view(), name="auth-me"),
    re_path(r"^password-reset/?$", AuthPasswordResetView.as_view(), name="auth-password-reset"),
    re_path(
        r"^password-reset/confirm/?$",
        AuthPasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
]
