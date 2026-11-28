from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        (
            "Профиль 3DPrint",
            {
                "fields": (
                    "role",
                    "phone",
                    "client_type",
                    "company_name",
                    "consent_at",
                    "is_senior",
                )
            },
        ),
    )
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "is_senior",
        "is_active",
    )
    list_filter = ("role", "client_type", "is_senior", "is_active", "is_staff")
