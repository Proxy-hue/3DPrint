from django.db import models
from django.db.models import F, Q

from common.models import BaseModel


class Assignment(BaseModel):
    """Назначение заказа на принтер (спецификация 5.2.1, таблица assignment).

    Текущее назначение заказа помечено ``is_current``; прежние хранятся.
    Цех определяется принтером. Обратная связь ``Order.assignments``
    используется модулем orders (фильтр заказов по цеху).

    Отличия от спецификации (нужны алгоритму):
    * ``material`` — материал задания: по нему считается штраф за смену
      материала на принтере (K_пер);
    * ``planned_hours`` — плановые часы печати для расчёта загрузки.
    """

    order = models.ForeignKey(
        'orders.Order', on_delete=models.CASCADE,
        related_name='assignments', verbose_name='Заказ',
    )
    printer = models.ForeignKey(
        'catalog.Printer', on_delete=models.PROTECT,
        related_name='assignments', verbose_name='Принтер',
    )
    material = models.ForeignKey(
        'catalog.Material', on_delete=models.PROTECT, null=True,
        blank=True, related_name='+', verbose_name='Материал',
    )
    planned_start = models.DateTimeField(verbose_name='Плановое начало')
    planned_end = models.DateTimeField(verbose_name='Плановое окончание')
    planned_hours = models.FloatField(default=0.0, verbose_name='Часы печати')
    is_manual = models.BooleanField(default=False, verbose_name='Вручную')
    reason = models.CharField(
        max_length=500, blank=True, verbose_name='Причина'
    )
    is_current = models.BooleanField(default=True, verbose_name='Текущее')

    class Meta:
        db_table = 'assignment'
        verbose_name = 'Назначение'
        verbose_name_plural = 'Назначения'
        ordering = ['-planned_start']
        indexes = [
            models.Index(
                fields=['printer', 'planned_start'],
                name='sched_asg_printer_start_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['order'],
                condition=Q(is_current=True),
                name='sched_one_current_assignment',
            ),
            models.CheckConstraint(
                condition=Q(planned_end__gte=F('planned_start')),
                name='sched_assignment_dates_valid',
            ),
        ]

    def __str__(self):
        return f'{self.order_id} -> {self.printer_id}'
