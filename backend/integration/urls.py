from django.urls import re_path

from .views import (
    IntegrationExportEventsView,
    IntegrationExportLoadView,
    IntegrationExportOrdersView,
    IntegrationOrderListView,
    IntegrationOrderModelDownloadView,
    IntegrationOrderStatusView,
)


urlpatterns = [
    re_path(r"^orders/?$", IntegrationOrderListView.as_view(), name="integration-order-list"),
    re_path(
        r"^orders/(?P<pk>\d+)/model/?$",
        IntegrationOrderModelDownloadView.as_view(),
        name="integration-order-model",
    ),
    re_path(
        r"^orders/(?P<pk>\d+)/status/?$",
        IntegrationOrderStatusView.as_view(),
        name="integration-order-status",
    ),
    re_path(
        r"^export/orders/?$",
        IntegrationExportOrdersView.as_view(),
        name="integration-export-orders",
    ),
    re_path(
        r"^export/events/?$",
        IntegrationExportEventsView.as_view(),
        name="integration-export-events",
    ),
    re_path(
        r"^export/load/?$",
        IntegrationExportLoadView.as_view(),
        name="integration-export-load",
    ),
]
