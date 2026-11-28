from django.contrib import admin

from common.admin import ReadOnlyAdminMixin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'order', 'amount', 'provider', 'status',
                    'created_at')
    list_filter = ('provider', 'status')
    search_fields = ('order__number',)
    list_select_related = ('order',)
