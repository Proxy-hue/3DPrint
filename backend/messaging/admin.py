from django.contrib import admin

from common.admin import ReadOnlyAdminMixin

from .models import Message


@admin.register(Message)
class MessageAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'order', 'author', 'model_version_num',
                    'created_at')
    search_fields = ('order__number', 'author__email')
    list_select_related = ('order', 'author')
