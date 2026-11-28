"""Тесты настройки Django admin: доступ по ролям, только чтение, аудит."""
import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from catalog.models import AuditLog
from orders.models import Order
from users.models import User

pytestmark = pytest.mark.django_db

SECTIONS = [
    'admin:users_user_changelist',
    'admin:orders_order_changelist',
    'admin:orders_orderevent_changelist',
    'admin:pricing_quote_changelist',
    'admin:messaging_message_changelist',
    'admin:notifications_notification_changelist',
    'admin:payment_payment_changelist',
    'admin:scheduling_assignment_changelist',
    'admin:catalog_technology_changelist',
    'admin:catalog_auditlog_changelist',
]


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email='admin@test.com', password='pass12345', role='ADMIN'
    )


@pytest.fixture
def manager_user():
    return User.objects.create_user(
        email='manager@test.com', password='pass12345', role='MANAGER',
        is_staff=True,
    )


@pytest.fixture
def client_user():
    return User.objects.create_user(
        email='client@test.com', password='pass12345', role='CLIENT'
    )


def test_manager_cannot_open_admin_sections(client, manager_user):
    client.force_login(manager_user)
    for name in SECTIONS:
        assert client.get(reverse(name)).status_code == 403, name


def test_admin_opens_all_sections(client, admin_user):
    client.force_login(admin_user)
    for name in SECTIONS:
        assert client.get(reverse(name)).status_code == 200, name


def test_orders_are_view_only_in_admin(client, admin_user, client_user):
    order = Order.objects.create(number='T-ADM-1', client=client_user)
    client.force_login(admin_user)
    assert client.get(
        reverse('admin:orders_order_change', args=[order.pk])
    ).status_code == 200
    assert client.post(
        reverse('admin:orders_order_change', args=[order.pk]),
        {'number': 'HACKED', 'status': 'COMPLETED'},
    ).status_code == 403
    assert client.get(reverse('admin:orders_order_add')).status_code == 403
    order.refresh_from_db()
    assert order.number == 'T-ADM-1'


def test_user_admin_sets_is_staff_by_role(admin_user, client_user):
    model_admin = admin.site._registry[User]
    request = RequestFactory().post('/')
    request.user = admin_user

    client_user.role = 'ADMIN'
    model_admin.save_model(request, client_user, form=None, change=True)
    client_user.refresh_from_db()
    assert client_user.is_staff is True

    client_user.role = 'MANAGER'
    model_admin.save_model(request, client_user, form=None, change=True)
    client_user.refresh_from_db()
    assert client_user.is_staff is False


def test_block_action_audits_without_password(client, admin_user, client_user):
    client.force_login(admin_user)
    response = client.post(reverse('admin:users_user_changelist'), {
        'action': 'block_users',
        '_selected_action': [str(client_user.pk), str(admin_user.pk)],
        'select_across': 0,
        'index': 0,
    })
    assert response.status_code == 302
    client_user.refresh_from_db()
    admin_user.refresh_from_db()
    assert client_user.is_active is False
    assert admin_user.is_active is True            # себя заблокировать нельзя

    entry = AuditLog.objects.get(entity_id=client_user.pk, action='UPDATE')
    assert entry.before['is_active'] is True
    assert entry.after['is_active'] is False
    assert 'password' not in entry.before and 'password' not in entry.after


def test_users_cannot_be_deleted_in_admin(client, admin_user, client_user):
    client.force_login(admin_user)
    response = client.post(
        reverse('admin:users_user_delete', args=[client_user.pk]),
        {'post': 'yes'},
    )
    assert response.status_code == 403
    assert User.objects.filter(pk=client_user.pk).exists()
