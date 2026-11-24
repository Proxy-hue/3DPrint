from django.urls import path

from .views import LoginView, LogoutView, ProfileView, RefreshView, RegisterView


urlpatterns = [
    path("register/", RegisterView.as_view(), name="user-register"),
    path("login/", LoginView.as_view(), name="user-login"),
    path("refresh/", RefreshView.as_view(), name="user-refresh"),
    path("me/", ProfileView.as_view(), name="user-profile"),
    path("logout/", LogoutView.as_view(), name="user-logout"),
]
