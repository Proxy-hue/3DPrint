from django.contrib import admin

from common.admin import ReadOnlyAdminMixin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Журнал уведомлений: видно неудачные отправки и число попыток."""

    list_display = ('id', 'user', 'channel', 'delivery_status', 'attempts',
                    'next_attempt_at', 'is_read', 'created_at')
    list_filter = ('channel', 'delivery_status', 'is_read')
    search_fields = ('user__email', 'order__number')
    list_select_related = ('user',)
