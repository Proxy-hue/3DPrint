from rest_framework import serializers

from .models import (
    Color, DeliveryMethod, Material, PickupPoint, PostProcessing, Printer,
    QualityProfile, Technology, Workshop,
)


class ReadOnlyModelSerializer(serializers.ModelSerializer):
    """Справочники в API только для чтения (правка — в Django admin)."""

    def get_extra_kwargs(self):
        extra = super().get_extra_kwargs()
        for name in self.Meta.fields:
            extra.setdefault(name, {})['read_only'] = True
        return extra


class WorkshopSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = Workshop
        fields = ['id', 'name', 'address', 'is_main', 'is_active']


class TechnologyPublicSerializer(ReadOnlyModelSerializer):
    """Для клиента: без тарифных коэффициентов."""

    class Meta:
        model = Technology
        fields = ['id', 'code', 'name']


class TechnologyDetailSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = Technology
        fields = ['id', 'code', 'name', 'fill_factor', 'support_factor',
                  'hourly_rate', 'setup_cost']


class QualityProfilePublicSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = QualityProfile
        fields = ['id', 'technology', 'name', 'layer_height_mm']


class QualityProfileDetailSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = QualityProfile
        fields = ['id', 'technology', 'name', 'layer_height_mm',
                  'flow_cm3_h', 'price_factor']


class ColorSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = Color
        fields = ['id', 'name', 'hex', 'is_transparent']


class MaterialPublicSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = Material
        fields = ['id', 'name', 'technologies', 'colors']


class MaterialDetailSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = Material
        fields = ['id', 'name', 'technologies', 'colors', 'density',
                  'price_per_gram', 'required_specialization']


class PostProcessingSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = PostProcessing
        fields = ['id', 'code', 'name', 'price', 'hours']


class DeliveryMethodSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = DeliveryMethod
        fields = ['id', 'type', 'name', 'price', 'days']


class PickupPointSerializer(ReadOnlyModelSerializer):
    class Meta:
        model = PickupPoint
        fields = ['id', 'delivery_method', 'name', 'address']


class PrinterSerializer(ReadOnlyModelSerializer):
    workshop_name = serializers.CharField(
        source='workshop.name', read_only=True
    )
    technology_code = serializers.CharField(
        source='technology.code', read_only=True
    )

    class Meta:
        model = Printer
        fields = ['id', 'name', 'workshop', 'workshop_name', 'technology',
                  'technology_code', 'max_x', 'max_y', 'max_z',
                  'specialization', 'status', 'materials']


# --- Матрица совместимости (GET /api/catalog/compatibility/) ---

class CompatMaterialSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    technologies = serializers.ListField(child=serializers.UUIDField())
    colors = serializers.ListField(child=serializers.UUIDField())


class CompatQualitySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    technology = serializers.UUIDField()


class CompatPostProcessingSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    code = serializers.CharField()
    incompatible_technologies = serializers.ListField(
        child=serializers.UUIDField()
    )
    forbids_transparent = serializers.BooleanField()
    requires_multibody_3mf = serializers.BooleanField()


class CompatDeliverySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    type = serializers.CharField()
    pickup_points = serializers.ListField(child=serializers.UUIDField())


class CompatibilitySerializer(serializers.Serializer):
    materials = CompatMaterialSerializer(many=True)
    quality_profiles = CompatQualitySerializer(many=True)
    post_processing = CompatPostProcessingSerializer(many=True)
    delivery_methods = CompatDeliverySerializer(many=True)
