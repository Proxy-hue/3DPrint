from rest_framework import serializers

from .services import SPEC_ENGINEERING_STATUSES


ALLOWED_TARGET_STATUSES = tuple(
    status for status in SPEC_ENGINEERING_STATUSES if status != "PAID"
)


class EngineeringStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=ALLOWED_TARGET_STATUSES,
        required=False,
        allow_null=True,
    )
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    actual_material_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    actual_material_g = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=3,
        min_value=0,
    )
    actual_print_hours = serializers.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=3,
        min_value=0,
    )
    printer_name = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=150,
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        has_any_field = any(
            key in attrs and attrs[key] is not None
            for key in (
                "status",
                "actual_material_name",
                "actual_material_g",
                "actual_print_hours",
                "printer_name",
                "notes",
            )
        )
        if not has_any_field:
            raise serializers.ValidationError(
                "Необходимо передать новый статус или хотя бы одно фактическое значение."
            )
        return attrs


class ExportFilterSerializer(serializers.Serializer):
    status = serializers.CharField(required=False, allow_blank=True)
    order_id = serializers.IntegerField(required=False, min_value=1)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    days = serializers.IntegerField(required=False, min_value=1, max_value=90, default=7)

    def validate(self, attrs):
        date_from = attrs.get("date_from")
        date_to = attrs.get("date_to")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise serializers.ValidationError(
                {"date_to": "Дата окончания не может быть раньше даты начала."}
            )
        return attrs
