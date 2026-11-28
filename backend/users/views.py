from axes.exceptions import AxesBackendPermissionDenied
from axes.handlers.proxy import AxesProxyHandler
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import (
    AuthLoginSerializer,
    AuthRegisterSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserSerializer,
)


def _confirm_password_reset(uid: str, token: str, new_password: str) -> Response:
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.filter(pk=user_id, is_active=True).first()
    except (TypeError, ValueError, OverflowError):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return Response(
            {
                "code": "INVALID_RESET_TOKEN",
                "message": "Ссылка восстановления недействительна или устарела.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    user.set_password(new_password)
    user.save(update_fields=("password", "updated_at"))
    return Response({"detail": "Пароль успешно обновлён."}, status=status.HTTP_200_OK)


@extend_schema(request=None, responses={200: None})
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def csrf_view(request):
    return Response({"csrfToken": get_token(request)})


class AuthRegisterView(APIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = AuthRegisterSerializer

    @extend_schema(request=AuthRegisterSerializer, responses={201: UserSerializer})
    def post(self, request):
        serializer = AuthRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class AuthLoginView(APIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = AuthLoginSerializer

    @extend_schema(request=AuthLoginSerializer, responses={200: UserSerializer})
    def post(self, request):
        serializer = AuthLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].strip().lower()
        password = serializer.validated_data["password"]
        credentials = {"username": email}

        if AxesProxyHandler.is_locked(request, credentials=credentials):
            return Response(
                {
                    "code": "ACCOUNT_LOCKED",
                    "message": "Учётная запись временно заблокирована после 5 неудачных попыток входа.",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        try:
            user = authenticate(request=request, username=email, password=password)
        except AxesBackendPermissionDenied:
            return Response(
                {
                    "code": "ACCOUNT_LOCKED",
                    "message": "Учётная запись временно заблокирована после 5 неудачных попыток входа.",
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        if user is None:
            return Response(
                {
                    "code": "INVALID_CREDENTIALS",
                    "message": "Неверный email или пароль.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {
                    "code": "USER_INACTIVE",
                    "message": "Учётная запись деактивирована.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        login(request, user)
        data = UserSerializer(user).data
        data["csrf_token"] = get_token(request)
        return Response(data, status=status.HTTP_200_OK)


class AuthLogoutView(APIView):
    permission_classes = (permissions.AllowAny,)

    @extend_schema(request=None, responses={200: None})
    def post(self, request):
        logout(request)
        return Response({"detail": "Сессия завершена."}, status=status.HTTP_200_OK)


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user


class AuthPasswordResetView(APIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = PasswordResetRequestSerializer

    @extend_schema(request=PasswordResetRequestSerializer, responses={200: None})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data.get("uid") and data.get("token"):
            return _confirm_password_reset(
                data["uid"],
                data["token"],
                data["new_password"],
            )

        email = data["email"].strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            send_mail(
                subject="Восстановление пароля — 3DPrint",
                message=(
                    f"Для восстановления пароля используйте параметры:\n"
                    f"uid: {uid}\n"
                    f"token: {token}\n"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=False,
            )
        return Response(
            {
                "detail": (
                    "Если пользователь с таким email зарегистрирован, "
                    "инструкция по восстановлению пароля отправлена."
                )
            },
            status=status.HTTP_200_OK,
        )


class AuthPasswordResetConfirmView(APIView):
    permission_classes = (permissions.AllowAny,)
    serializer_class = PasswordResetConfirmSerializer

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: None})
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return _confirm_password_reset(data["uid"], data["token"], data["new_password"])
