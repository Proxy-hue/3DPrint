from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    id = serializers.CharField(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "role",
            "full_name",
            "first_name",
            "last_name",
            "phone",
            "client_type",
            "company_name",
            "consent_at",
            "is_senior",
        )
        read_only_fields = ("id", "email", "role", "consent_at", "is_senior", "full_name")

    def get_full_name(self, obj: User) -> str:
        return obj.get_full_name() or obj.email


class AuthRegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    client_type = serializers.ChoiceField(
        choices=User.ClientType.choices,
        required=False,
        default=User.ClientType.INDIVIDUAL,
    )
    company_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    consent = serializers.BooleanField(required=True)

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        return email

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Необходимо согласие на обработку персональных данных.")
        return value

    def validate(self, attrs):
        full_name = (attrs.get("full_name") or "").strip()
        first_name = (attrs.get("first_name") or "").strip()
        last_name = (attrs.get("last_name") or "").strip()
        if not first_name and not last_name and full_name:
            parts = full_name.split(None, 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""
        attrs["first_name"] = first_name
        attrs["last_name"] = last_name
        if (
            attrs.get("client_type") == User.ClientType.ORGANIZATION
            and not attrs.get("company_name", "").strip()
        ):
            raise serializers.ValidationError(
                {"company_name": "Для организации укажите название компании."}
            )
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            phone=validated_data.get("phone", ""),
            client_type=validated_data.get("client_type", User.ClientType.INDIVIDUAL),
            company_name=validated_data.get("company_name", ""),
            consent_at=timezone.now(),
            role=User.Role.CLIENT,
        )


class AuthLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    uid = serializers.CharField(required=False)
    token = serializers.CharField(required=False)
    new_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    def validate(self, attrs):
        has_email = bool(attrs.get("email"))
        has_confirm = all(attrs.get(field) for field in ("uid", "token", "new_password"))
        if not has_email and not has_confirm:
            raise serializers.ValidationError(
                "Укажите email для запроса сброса или uid, token и new_password для подтверждения."
            )
        if has_confirm:
            validate_password(attrs["new_password"])
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value):
        validate_password(value)
        return value
