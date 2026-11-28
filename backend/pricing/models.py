from django.db import models

from common.models import BaseModel


class Quote(BaseModel):
    """Расчёт стоимости и срока выполнения заказа (спецификация 5.3.3)."""

    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE, related_name='quotes',
    )
    tariff_version = models.ForeignKey(
        'catalog.TariffVersion', null=True, blank=True,
        on_delete=models.PROTECT, related_name='+',
    )
    cost_material = models.DecimalField(max_digits=12, decimal_places=2)
    cost_machine = models.DecimalField(max_digits=12, decimal_places=2)
    cost_post = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cost_delivery = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    adjustment = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=0)
    print_hours = models.DecimalField(max_digits=10, decimal_places=2)
    mass_g = models.DecimalField(max_digits=12, decimal_places=2)
    estimated_days = models.PositiveIntegerField()
    is_current = models.BooleanField(default=True)

    class Meta:
        db_table = 'quote'
        constraints = [
            models.CheckConstraint(condition=models.Q(total__gte=0), name='quote_total_gte_0'),
        ]
        indexes = [models.Index(fields=['order', 'is_current'])]
        ordering = ['-created_at']

    def __str__(self):
        return f'Quote {self.order_id}: {self.total} ₽'
