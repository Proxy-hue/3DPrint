from rest_framework import serializers


class PrinterLoadSerializer(serializers.Serializer):
    printer_id = serializers.UUIDField()
    printer_name = serializers.CharField()
    workshop_id = serializers.UUIDField()
    workshop_name = serializers.CharField()
    planned_hours = serializers.FloatField()
    load_percent = serializers.FloatField()
    idle_hours = serializers.FloatField()


class WorkshopLoadSerializer(serializers.Serializer):
    workshop_id = serializers.UUIDField()
    workshop_name = serializers.CharField()
    load_percent = serializers.FloatField()


class LoadSerializer(serializers.Serializer):
    horizon_days = serializers.IntegerField()
    capacity_hours = serializers.FloatField()
    printers = PrinterLoadSerializer(many=True)
    workshops = WorkshopLoadSerializer(many=True)
