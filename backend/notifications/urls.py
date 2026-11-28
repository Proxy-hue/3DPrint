from django.urls import path

from . import views

urlpatterns = [
    path('notifications', views.NotificationList.as_view(), name='notification-list'),
    path('notifications/read-all', views.NotificationReadAll.as_view(), name='notification-read-all'),
    path('notifications/<uuid:pk>/read', views.NotificationRead.as_view(), name='notification-read'),
]
