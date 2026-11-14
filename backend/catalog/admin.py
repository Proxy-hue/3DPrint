from django.contrib import admin
from .models import (
    Workshop, Technology, QualityProfile,
    Material, Color, Printer
)


@admin.register(Workshop)
class WorkshopAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_main', 'address')


@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'hourly_rate')


@admin.register(QualityProfile)
class QualityProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'technology', 'layer_height')
    list_filter = ('technology',)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('name', 'technology', 'price_per_gram', 'density')
    list_filter = ('technology',)


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ('name', 'hex_code')


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = ('name', 'workshop', 'technology', 'status')
    list_filter = ('workshop', 'technology', 'status')
