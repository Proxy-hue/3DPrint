"""Публичный интерфейс уведомлений: INAPP всегда сохраняется, EMAIL — с повторами (5, 15, 60 мин)."""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from orders.tasks import enqueue

from .models import Notification

RETRY_MINUTES = [5, 15, 60]


def notify(user, text, order=None):
    inapp = Notification.objects.create(
        user=user, order=order, channel=Notification.Channel.INAPP,
        text=text, delivery_status='DELIVERED',
    )
    if getattr(user, 'email', None):
        email = Notification.objects.create(
            user=user, order=order, channel=Notification.Channel.EMAIL,
            text=text, delivery_status='PENDING', next_attempt_at=timezone.now(),
        )
        enqueue('notifications.services.send_email_notification', str(email.id))
    return inapp


def send_email_notification(notification_id):
    n = Notification.objects.select_related('user', 'order').filter(pk=notification_id).first()
    if not n or n.delivery_status in ('DELIVERED', 'FAILED'):
        return
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
    n.save()


def retry_due_emails():
    ids = list(
        Notification.objects.filter(
            channel='EMAIL',
            delivery_status__in=('PENDING', 'RETRY'),
            next_attempt_at__lte=timezone.now(),
        ).values_list('id', flat=True)
    )
    for i in ids:
        send_email_notification(i)
    return len(ids)
