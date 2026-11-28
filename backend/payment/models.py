from django.db import models

from common.models import BaseModel


class Payment(BaseModel):
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    provider = models.CharField(max_length=32, default='STUB')
    status = models.CharField(max_length=16, default='PENDING')

    class Meta:
        db_table = 'payment'

    def __str__(self):
        return f'Payment {self.order_id}: {self.amount} ({self.status})'
