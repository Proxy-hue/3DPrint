from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from catalog.admin import AuditMixin
from catalog.audit import record, snapshot
from common.admin import AdminRoleMixin
from common.permissions import ADMIN, CLIENT, MANAGER

from .models import User

ROLE_CHOICES = [
    (CLIENT, "Клиент"),
    (MANAGER, "Менеджер"),
    (ADMIN, "Администратор"),
]


@admin.register(User)
class UserAdmin(AdminRoleMixin, AuditMixin, BaseUserAdmin):
    """Управление пользователями и ролями (F-MGR-11)."""

    ordering = ["email"]
    list_display = [
        "email",
        "full_name",
        "role",
        "client_type",
        "is_senior",
        "is_active",
        "is_staff",
        "date_joined",
    ]
    list_filter = ["role", "client_type", "is_senior", "is_active"]
    search_fields = ["email", "first_name", "last_name", "phone", "company_name"]
    actions = ["block_users", "unblock_users"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Личные данные",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone",
                    "client_type",
                    "company_name",
                    "consent_at",
                )
            },
        ),
        (
            "Права",
            {
                "fields": (
                    "role",
                    "is_senior",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
    )

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2", "role", "is_senior"),
            },
        ),
    )

    @admin.display(description="Имя")
    def full_name(self, obj):
        return obj.get_full_name()

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == "role":
            return forms.ChoiceField(choices=ROLE_CHOICES, label="Роль")
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        readonly = tuple(super().get_readonly_fields(request, obj))
        if obj is not None and obj.pk == request.user.pk:
            readonly += ("role", "is_active", "is_superuser")
        return readonly

    def save_model(self, request, obj, form, change):
        obj.is_staff = bool(obj.is_superuser or obj.role == ADMIN)
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False

    def _set_active(self, request, queryset, active):
        changed = 0
        for user in queryset.exclude(pk=request.user.pk):
            if user.is_active == active:
                continue
            before = snapshot(user)
            user.is_active = active
            user.save(update_fields=["is_active"])
            record(request.user, user, "UPDATE", before, snapshot(user))
            changed += 1
        self.message_user(
            request,
            f'{"Разблокировано" if active else "Заблокировано"}: {changed}. '
            f"Свой аккаунт заблокировать нельзя.",
            messages.SUCCESS,
        )

    @admin.action(description="Заблокировать выбранных пользователей")
    def block_users(self, request, queryset):
        self._set_active(request, queryset, False)

    @admin.action(description="Разблокировать выбранных пользователей")
    def unblock_users(self, request, queryset):
        self._set_active(request, queryset, True)
