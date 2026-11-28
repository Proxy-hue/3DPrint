"""Временные эндпоинты сессионной аутентификации для автономного запуска клиентского портала.

ВНИМАНИЕ: Аутентификация и управление пользователями относятся к зоне ответственности
П. А. Юшковой (`users`). Эти временные маршруты вынесены за пределы модуля `users`,
чтобы не менять чужие файлы и обеспечить локальную проверку клиентского портала до
интеграции `users`.
"""
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.middleware.csrf import get_token
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .permissions import CLIENT, get_role

User = get_user_model()


def _user_dto(user):
    return {
        'id': str(user.id),
        'email': user.email,
        'role': get_role(user) or user.role,
        'full_name': getattr(user, 'full_name', '') or user.get_full_name() or user.email,
        'phone': getattr(user, 'phone', ''),
        'client_type': getattr(user, 'client_type', 'INDIVIDUAL'),
        'company_name': getattr(user, 'company_name', ''),
        'is_senior': bool(getattr(user, 'is_senior', False)),
    }


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def csrf_view(request):
    return Response({'csrfToken': get_token(request)})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_view(request):
    data = request.data or {}
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    full_name = str(data.get('full_name', '')).strip()
    if not data.get('consent'):
        return Response({'detail': 'Необходимо согласие на обработку персональных данных.'}, status=400)
    if not email or '@' not in email:
        return Response({'detail': 'Укажите корректный email.'}, status=400)
    if User.objects.filter(email__iexact=email).exists():
        return Response({'detail': 'Пользователь с таким email уже существует.'}, status=400)
    try:
        validate_password(password)
    except DjangoValidationError as e:
        return Response({'detail': ' '.join(e.messages)}, status=400)

    parts = full_name.split(None, 1)
    first_name = parts[0] if parts else ''
    last_name = parts[1] if len(parts) > 1 else ''
    user = User.objects.create_user(
        email=email,
        password=password,
        role=CLIENT,
        first_name=first_name,
        last_name=last_name,
        phone=str(data.get('phone', ''))[:20],
        company_name=str(data.get('company_name', ''))[:255],
    )
    login(request, user)
    return Response(_user_dto(user), status=201)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login_view(request):
    data = request.data or {}
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    user = authenticate(request, username=email, password=password)
    if user is None or not user.is_active:
        return Response({'detail': 'Неверный email или пароль.'}, status=400)
    login(request, user)
    return Response(_user_dto(user))


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout_view(request):
    logout(request)
    return Response({'detail': 'Выход выполнен.'})


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def me_view(request):
    return Response(_user_dto(request.user))


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_view(request):
    email = str((request.data or {}).get('email', '')).strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        base_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173').rstrip('/')
        send_mail(
            '3DPrint: восстановление пароля',
            f'Ссылка для сброса: {base_url}/reset-password/{uid}/{token}',
            'noreply@3dprint.local',
            [user.email],
            fail_silently=True,
        )
    return Response({'detail': 'Если email зарегистрирован, инструкция отправлена.'})


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def password_reset_confirm_view(request):
    data = request.data or {}
    try:
        uid = force_str(urlsafe_base64_decode(str(data.get('uid', ''))))
        user = User.objects.get(pk=uid)
    except Exception:
        return Response({'detail': 'Недействительная ссылка сброса пароля.'}, status=400)
    if not default_token_generator.check_token(user, str(data.get('token', ''))):
        return Response({'detail': 'Ссылка сброса пароля недействительна или её срок действия истёк.'}, status=400)
    password = str(data.get('password', ''))
    try:
        validate_password(password, user=user)
    except DjangoValidationError as e:
        return Response({'detail': ' '.join(e.messages)}, status=400)
    user.set_password(password)
    user.save(update_fields=['password'])
    return Response({'detail': 'Пароль изменён.'})
