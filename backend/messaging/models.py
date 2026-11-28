from django.conf import settings
from django.db import models

from common.models import BaseModel


class Message(BaseModel):
    """Сообщение по заказу (спецификация 5.3.3)."""

    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='messages',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+',
    )
    text = models.TextField()
    model_version_id = models.UUIDField(null=True, blank=True)
    model_version_num = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = 'message'
        ordering = ['created_at']

    def __str__(self):
        return f'Message {self.order_id} by {self.author_id}'
