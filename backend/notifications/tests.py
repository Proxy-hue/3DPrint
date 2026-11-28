"""Тесты модуля notifications: INAPP/EMAIL доставка, ретраи [5, 15, 60], REST API и команда."""
import pytest
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from notifications import services as ns
from notifications.models import Notification
from users.models import User

pytestmark = pytest.mark.django_db


class FailingEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise ConnectionError('SMTP server unavailable')


@pytest.fixture
def notif_users():
    return {
        'u1': User.objects.create_user(email='u1@test.local', password='pass12345', role='CLIENT'),
        'u2': User.objects.create_user(email='u2@test.local', password='pass12345', role='CLIENT'),
    }


def test_notify_creates_inapp_and_delivers_email(notif_users):
    u1 = notif_users['u1']
    inapp = ns.notify(u1, 'Тестовое уведомление')
    assert inapp.channel == 'INAPP'
    assert inapp.delivery_status == 'DELIVERED'

    email_rec = Notification.objects.get(user=u1, channel='EMAIL')
    assert email_rec.delivery_status == 'DELIVERED'
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ['u1@test.local']


def test_email_retry_schedule_5_15_60_and_failed(notif_users, settings):
    settings.EMAIL_BACKEND = 'notifications.tests.FailingEmailBackend'
    n = Notification.objects.create(
        user=notif_users['u1'], channel='EMAIL', text='x', delivery_status='PENDING',
    )
    expected = [(5, 'RETRY'), (15, 'RETRY'), (60, 'RETRY'), (None, 'FAILED')]
    for minutes, status in expected:
        before = timezone.now()
        ns.send_email_notification(n.pk)
        n.refresh_from_db()
        assert n.delivery_status == status
        if minutes is not None:
            delta = (n.next_attempt_at - before).total_seconds() / 60
            assert minutes - 0.5 < delta < minutes + 0.5
        else:
            assert n.next_attempt_at is None


def test_retry_due_emails_and_management_command(notif_users):
    Notification.objects.create(
        user=notif_users['u1'],
        channel='EMAIL',
        text='due',
        delivery_status='RETRY',
        next_attempt_at=timezone.now(),
    )
    call_command('retry_notifications')
    assert len(mail.outbox) == 1
    assert Notification.objects.get(channel='EMAIL').delivery_status == 'DELIVERED'


def test_notifications_api_and_read_isolation(notif_users):
    u1, u2 = notif_users['u1'], notif_users['u2']
    n1 = Notification.objects.create(user=u1, channel='INAPP', text='Привет', delivery_status='DELIVERED')
    Notification.objects.create(user=u2, channel='INAPP', text='Чужое', delivery_status='DELIVERED')

    api = APIClient()
    api.force_authenticate(u1)

    r_list = api.get('/api/notifications')
    assert r_list.status_code == 200
    assert r_list.data['unread'] == 1
    assert len(r_list.data['results']) == 1

    r_read = api.post(f'/api/notifications/{n1.pk}/read')
    assert r_read.status_code == 200
    assert r_read.data['is_read'] is True
    assert api.get('/api/notifications').data['unread'] == 0

    n2 = Notification.objects.get(user=u2)
    assert api.post(f'/api/notifications/{n2.pk}/read').status_code == 404
