from rest_framework import serializers


class ValidationRequestSerializer(serializers.Serializer):
    file = serializers.FileField(allow_empty_file=True)
