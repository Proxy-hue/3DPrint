from django.urls import path

from . import views

urlpatterns = [
    path('orders', views.OrderListCreate.as_view(), name='order-list-create'),
    path('orders/<uuid:pk>', views.OrderDetail.as_view(), name='order-detail'),
    path('orders/<uuid:pk>/model', views.ModelUpload.as_view(), name='order-model-upload'),
    path('orders/<uuid:pk>/model/<int:v>/file', views.ModelFile.as_view(), name='order-model-file'),
    path('orders/<uuid:pk>/model/<int:v>/download', views.ModelDownload.as_view(), name='order-model-download'),
    path('orders/<uuid:pk>/quote', views.OrderQuote.as_view(), name='order-quote'),
    path('orders/<uuid:pk>/confirm', views.OrderConfirm.as_view(), name='order-confirm'),
    path('orders/<uuid:pk>/pay', views.OrderPay.as_view(), name='order-pay'),
    path('orders/<uuid:pk>/cancel', views.OrderCancel.as_view(), name='order-cancel'),
    path('orders/<uuid:pk>/repeat', views.OrderRepeat.as_view(), name='order-repeat'),
    path('orders/<uuid:pk>/decision', views.OrderDecision.as_view(), name='order-decision'),
    path('orders/<uuid:pk>/status', views.OrderStatus.as_view(), name='order-status'),
    path('orders/<uuid:pk>/priority', views.OrderPriority.as_view(), name='order-priority'),
    path('orders/<uuid:pk>/adjustment', views.OrderAdjustment.as_view(), name='order-adjustment'),
    path('orders/<uuid:pk>/messages', views.OrderMessages.as_view(), name='order-messages'),
    path('orders/<uuid:pk>/recommendation', views.OrderRecommendation.as_view(), name='order-recommendation'),
    path('orders/<uuid:pk>/assignment', views.OrderAssignment.as_view(), name='order-assignment'),
]
