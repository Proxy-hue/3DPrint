from rest_framework import serializers
from .models import (
    Workshop, Technology, QualityProfile,
    Material, Color, Printer
)


class WorkshopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workshop
        fields = ['id', 'name', 'address', 'is_main']


class TechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Technology
        fields = ['id', 'code', 'name', 'fill_factor', 'hourly_rate']


class QualityProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = QualityProfile
        fields = ['id', 'technology', 'name', 'layer_height', 'flow_rate']


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ['id', 'name', 'density', 'price_per_gram', 'technology']


class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = ['id', 'name', 'hex_code']


class PrinterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Printer
        fields = ['id', 'name', 'Workshop', 'technology', 'max_x', 'max_y',
                  'max_z', 'status']
