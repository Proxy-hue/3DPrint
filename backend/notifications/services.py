"""Публичный интерфейс уведомлений: INAPP всегда сохраняется, EMAIL — с повторами (5, 15, 60 мин)."""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from orders.tasks import enqueue

from .models import Notification

RETRY_MINUTES = [5, 15, 60]
SENDING_STALE_MINUTES = 10


def notify(user, text, order=None):
    inapp = Notification.objects.create(
        user=user, order=order, channel=Notification.Channel.INAPP,
        text=text, delivery_status='DELIVERED',
    )
    if getattr(user, 'email', None):
        email = Notification.objects.create(
            user=user, order=order, channel=Notification.Channel.EMAIL,
            text=text, delivery_status='PENDING',
            next_attempt_at=timezone.now() + timedelta(minutes=RETRY_MINUTES[0]),
        )
        enqueue('notifications.services.send_email_notification', str(email.id))
    return inapp


def send_email_notification(notification_id):
    with transaction.atomic():
        n = (
            Notification.objects.select_for_update(skip_locked=True, of=('self',))
            .select_related('user', 'order')
            .filter(pk=notification_id)
            .first()
        )
        stale_before = timezone.now() - timedelta(minutes=SENDING_STALE_MINUTES)
        is_stale_sending = (
            n is not None and n.delivery_status == 'SENDING' and n.updated_at <= stale_before
        )
        if not n or (n.delivery_status not in ('PENDING', 'RETRY') and not is_stale_sending):
            return
        n.delivery_status = 'SENDING'
        n.save(update_fields=['delivery_status', 'updated_at'])

    subject = f'3DPrint: заказ {n.order.number}' if n.order else '3DPrint: уведомление'
    try:
        send_mail(
            subject, n.text,
            getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@3dprint.local'),
            [n.user.email], fail_silently=False,
        )
        n.delivery_status, n.next_attempt_at = 'DELIVERED', None
    except Exception:
        n.attempts += 1
        if n.attempts > len(RETRY_MINUTES):
            n.delivery_status, n.next_attempt_at = 'FAILED', None
        else:
            n.delivery_status = 'RETRY'
            n.next_attempt_at = timezone.now() + timedelta(minutes=RETRY_MINUTES[n.attempts - 1])
    n.save(update_fields=['delivery_status', 'attempts', 'next_attempt_at', 'updated_at'])


def retry_due_emails():
    now = timezone.now()
    ids = list(
        Notification.objects.filter(channel='EMAIL').filter(
            Q(delivery_status__in=('PENDING', 'RETRY'), next_attempt_at__lte=now)
            | Q(delivery_status='SENDING', updated_at__lte=now - timedelta(minutes=SENDING_STALE_MINUTES))
        ).values_list('id', flat=True)
    )
    for i in ids:
        send_email_notification(i)
    return len(ids)
