from django.conf import settings
from django.db import models

from common.models import BaseModel


class Status(models.TextChoices):
    DRAFT = 'DRAFT', 'Черновик'
    NEW = 'NEW', 'Новый'
    CHECKED = 'CHECKED', 'Проверен'
    MANUAL_REVIEW = 'MANUAL_REVIEW', 'Ручная проверка'
    CLARIFICATION = 'CLARIFICATION', 'Требуется уточнение'
    AWAITING_PAYMENT = 'AWAITING_PAYMENT', 'Ожидает оплаты'
    PAID = 'PAID', 'Оплачен'
    DISTRIBUTED = 'DISTRIBUTED', 'Распределён'
    PRINTING = 'PRINTING', 'В печати'
    POST_PROCESSING = 'POST_PROCESSING', 'Постобработка'
    READY = 'READY', 'Готов к выдаче'
    COMPLETED = 'COMPLETED', 'Выполнен'
    REJECTED = 'REJECTED', 'Отклонён'
    CANCELLED = 'CANCELLED', 'Отменён'


class Order(BaseModel):
    """Заказ на 3D-печать (спецификация 5.3.3)."""

    number = models.CharField(max_length=24, unique=True)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='orders',
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    priority = models.PositiveSmallIntegerField(default=0)  # 0 — обычный, 1 — высокий
    quantity = models.PositiveIntegerField(default=1)
    material = models.ForeignKey(
        'catalog.Material', null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    technology = models.ForeignKey(
        'catalog.Technology', null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    quality_profile = models.ForeignKey(
        'catalog.QualityProfile', null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    color = models.ForeignKey(
        'catalog.Color', null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    delivery_method = models.ForeignKey(
        'catalog.DeliveryMethod', null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    pickup_point = models.ForeignKey(
        'catalog.PickupPoint', null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    delivery_address = models.CharField(max_length=255, blank=True, default='')
    desired_date = models.DateField(null=True, blank=True)
    planned_date = models.DateField(null=True, blank=True)
    reject_reason = models.TextField(blank=True, default='')
    comment = models.TextField(blank=True, default='')
    version = models.PositiveIntegerField(default=1)  # оптимистичная блокировка
    post_processings = models.ManyToManyField(
        'catalog.PostProcessing', through='OrderPostProcessing', related_name='+',
    )
    # Временное хранилище метаданных модели и проверки, пока модули models_app и validation
    # находятся в разработке у коллег (автоматически делегируется им при интеграции).
    model_meta = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'order'
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name='order_quantity_gte_1'),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['client']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return self.number


class OrderPostProcessing(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE)
    post_processing = models.ForeignKey('catalog.PostProcessing', on_delete=models.PROTECT)

    class Meta:
        db_table = 'order_post_processing'
        constraints = [
            models.UniqueConstraint(fields=['order', 'post_processing'], name='uniq_order_pp'),
        ]


class InsertOnlyError(Exception):
    pass


class OrderEvent(BaseModel):
    """Журнал событий заказа (только вставка — INSERT ONLY, спецификация 5.3.3)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='events')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+',
    )
    type = models.CharField(max_length=48)
    from_status = models.CharField(max_length=24, blank=True, default='')
    to_status = models.CharField(max_length=24, blank=True, default='')
    reason = models.TextField(blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'order_event'
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise InsertOnlyError('Запись только для добавления (INSERT-ONLY).')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise InsertOnlyError('Запись только для добавления (INSERT-ONLY).')
