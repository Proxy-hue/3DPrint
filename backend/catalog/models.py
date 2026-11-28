from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Q

from common.models import BaseModel

from .dto import (
    DELIVERY_COURIER, DELIVERY_PICKUP, PRINTER_ACTIVE, PRINTER_MAINTENANCE,
    PRINTER_RETIRED, SPEC_HIGH_STRENGTH_RESIN, SPEC_LARGE_FORMAT, SPEC_METAL,
    SPEC_NONE, default_tariff_params,
)


class Specialization(models.TextChoices):
    NONE = SPEC_NONE, 'Нет'
    METAL = SPEC_METAL, 'Металл'
    HIGH_STRENGTH_RESIN = (
        SPEC_HIGH_STRENGTH_RESIN, 'Высокопрочные смолы'
    )
    LARGE_FORMAT = SPEC_LARGE_FORMAT, 'Крупногабаритный'


# Специализация, которую может требовать материал (крупногабаритность
# определяется размерами модели, а не материалом).
MATERIAL_SPECIALIZATIONS = [
    (SPEC_NONE, 'Нет'),
    (SPEC_METAL, 'Металл'),
    (SPEC_HIGH_STRENGTH_RESIN, 'Высокопрочные смолы'),
]


class CatalogModel(BaseModel):
    """Справочная сущность: не удаляется, а деактивируется."""

    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        abstract = True


class Workshop(CatalogModel):
    name = models.CharField(max_length=100, verbose_name='Название цеха')
    address = models.CharField(
        max_length=255, blank=True, verbose_name='Адрес'
    )
    is_main = models.BooleanField(default=False, verbose_name='Основной цех')

    class Meta:
        verbose_name = 'Цех'
        verbose_name_plural = 'Цеха'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['is_main'],
                condition=Q(is_main=True),
                name='catalog_single_main_workshop',
            ),
        ]

    def __str__(self):
        return self.name


class Technology(CatalogModel):
    code = models.CharField(
        max_length=20, unique=True, verbose_name='Код (FDM, SLA, DMLS)'
    )
    name = models.CharField(max_length=100, verbose_name='Название')
    fill_factor = models.FloatField(
        default=1.0,
        validators=[MinValueValidator(0.01), MaxValueValidator(1.0)],
        verbose_name='Коэффициент заполнения φ',
    )
    support_factor = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0)],
        verbose_name='Коэффициент поддержек σ',
    )
    hourly_rate = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Стоимость машино-часа R (₽)',
    )
    setup_cost = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)],
        verbose_name='Стоимость подготовки S (₽)',
    )

    class Meta:
        verbose_name = 'Технология'
        verbose_name_plural = 'Технологии'
        ordering = ['code']

    def __str__(self):
        return f'{self.code} - {self.name}'


class QualityProfile(CatalogModel):
    technology = models.ForeignKey(
        Technology, on_delete=models.PROTECT,
        related_name='quality_profiles', verbose_name='Технология',
    )
    name = models.CharField(max_length=100, verbose_name='Название профиля')
    layer_height_mm = models.FloatField(
        validators=[MinValueValidator(0.001)],
        verbose_name='Толщина слоя (мм)',
    )
    flow_cm3_h = models.FloatField(
        validators=[MinValueValidator(0.1)],
        verbose_name='Поток печати Q (см³/ч)',
    )
    price_factor = models.FloatField(
        default=1.0, validators=[MinValueValidator(0.1)],
        verbose_name='Коэффициент цены k',
    )

    class Meta:
        verbose_name = 'Профиль качества'
        verbose_name_plural = 'Профили качества'
        ordering = ['technology__code', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['technology', 'name'],
                name='catalog_quality_unique_per_technology',
            ),
        ]

    def __str__(self):
        return f'{self.technology.code} - {self.name}'


class Color(CatalogModel):
    name = models.CharField(max_length=50, verbose_name='Название цвета')
    hex = models.CharField(
        max_length=7, blank=True, verbose_name='HEX-код'
    )
    # Отличие от спецификации 5.3.3: прозрачность — свойство цвета
    # (у «Стандартной смолы» есть и серый, и прозрачный; приложение 6).
    is_transparent = models.BooleanField(
        default=False, verbose_name='Прозрачный'
    )

    class Meta:
        verbose_name = 'Цвет'
        verbose_name_plural = 'Цвета'
        ordering = ['name']

    def __str__(self):
        return self.name


class Material(CatalogModel):
    name = models.CharField(max_length=100, verbose_name='Название материала')
    density = models.FloatField(
        validators=[MinValueValidator(0.1)],
        verbose_name='Плотность ρ (г/см³)',
    )
    price_per_gram = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name='Цена p (₽/г)',
    )
    required_specialization = models.CharField(
        max_length=20, choices=MATERIAL_SPECIALIZATIONS,
        default=SPEC_NONE,
        verbose_name='Требуемая специализация принтера',
    )
    technologies = models.ManyToManyField(
        Technology, related_name='materials', blank=True,
        verbose_name='Допустимые технологии',
    )
    colors = models.ManyToManyField(
        Color, related_name='materials', blank=True,
        verbose_name='Доступные цвета',
    )

    class Meta:
        verbose_name = 'Материал'
        verbose_name_plural = 'Материалы'
        ordering = ['name']

    def __str__(self):
        return self.name


class PostProcessing(CatalogModel):
    code = models.CharField(
        max_length=20, unique=True,
        verbose_name='Код (SANDING, PAINTING, ASSEMBLY)',
    )
    name = models.CharField(max_length=100, verbose_name='Название')
    price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)],
        verbose_name='Цена за изделие (₽)',
    )
    hours = models.FloatField(
        validators=[MinValueValidator(0.0)],
        verbose_name='Часов на изделие',
    )
    incompatible_technologies = models.ManyToManyField(
        Technology, blank=True, related_name='incompatible_post_processings',
        verbose_name='Недоступна для технологий',
    )
    forbids_transparent = models.BooleanField(
        default=False, verbose_name='Недоступна для прозрачных цветов'
    )
    requires_multibody_3mf = models.BooleanField(
        default=False,
        verbose_name='Только для 3MF с несколькими телами',
    )

    class Meta:
        verbose_name = 'Постобработка'
        verbose_name_plural = 'Постобработка'
        ordering = ['name']

    def __str__(self):
        return self.name


class DeliveryMethod(CatalogModel):
    TYPE_CHOICES = (
        (DELIVERY_PICKUP, 'Самовывоз'),
        (DELIVERY_COURIER, 'Курьерская доставка'),
    )

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    name = models.CharField(max_length=100, verbose_name='Название')
    price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        validators=[MinValueValidator(0)], verbose_name='Цена (₽)',
    )
    days = models.PositiveSmallIntegerField(
        default=0, verbose_name='Срок (сут.)'
    )

    class Meta:
        verbose_name = 'Способ получения'
        verbose_name_plural = 'Способы получения'
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=Q(type__in=[DELIVERY_PICKUP, DELIVERY_COURIER]),
                name='catalog_delivery_type_valid',
            ),
        ]

    def __str__(self):
        return self.name


class PickupPoint(CatalogModel):
    delivery_method = models.ForeignKey(
        DeliveryMethod, on_delete=models.PROTECT,
        related_name='pickup_points',
        limit_choices_to={'type': DELIVERY_PICKUP},
        verbose_name='Способ получения',
    )
    name = models.CharField(max_length=100, verbose_name='Название')
    address = models.CharField(max_length=255, verbose_name='Адрес')

    class Meta:
        verbose_name = 'Пункт выдачи'
        verbose_name_plural = 'Пункты выдачи'
        ordering = ['name']

    def __str__(self):
        return self.name


class TariffVersion(BaseModel):
    """Версия тарифов и параметров расчёта.

    Изменение тарифов = новая версия; расчёты ранее созданных заказов
    не меняются. Активна ровно одна версия.
    """

    params = models.JSONField(
        default=default_tariff_params, verbose_name='Параметры'
    )
    is_active = models.BooleanField(default=False, verbose_name='Активна')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
        verbose_name='Автор',
    )

    class Meta:
        verbose_name = 'Версия тарифов'
        verbose_name_plural = 'Версии тарифов'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['is_active'],
                condition=Q(is_active=True),
                name='catalog_single_active_tariff',
            ),
        ]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_active:
                TariffVersion.objects.exclude(pk=self.pk).filter(
                    is_active=True
                ).update(is_active=False)
            super().save(*args, **kwargs)

    def __str__(self):
        if self.created_at is None:
            return 'Новая версия тарифов'
        return f'Тарифы от {self.created_at:%Y-%m-%d %H:%M}'


class Printer(BaseModel):
    STATUS_CHOICES = (
        (PRINTER_ACTIVE, 'В работе'),
        (PRINTER_MAINTENANCE, 'Обслуживание'),
        (PRINTER_RETIRED, 'Списан'),
    )

    name = models.CharField(max_length=100, verbose_name='Название принтера')
    workshop = models.ForeignKey(
        Workshop, on_delete=models.PROTECT, related_name='printers',
        verbose_name='Цех',
    )
    technology = models.ForeignKey(
        Technology, on_delete=models.PROTECT, related_name='printers',
        verbose_name='Технология',
    )
    max_x = models.IntegerField(
        validators=[MinValueValidator(1)], verbose_name='Макс. X (мм)'
    )
    max_y = models.IntegerField(
        validators=[MinValueValidator(1)], verbose_name='Макс. Y (мм)'
    )
    max_z = models.IntegerField(
        validators=[MinValueValidator(1)], verbose_name='Макс. Z (мм)'
    )
    specialization = models.CharField(
        max_length=20, choices=Specialization.choices,
        default=SPEC_NONE, verbose_name='Специализация',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=PRINTER_ACTIVE,
        verbose_name='Статус',
    )
    materials = models.ManyToManyField(
        Material, related_name='printers', blank=True,
        verbose_name='Поддерживаемые материалы',
    )

    class Meta:
        verbose_name = 'Принтер'
        verbose_name_plural = 'Принтеры'
        ordering = ['name']
        constraints = [
            models.CheckConstraint(
                condition=Q(max_x__gt=0, max_y__gt=0, max_z__gt=0),
                name='catalog_printer_dims_positive',
            ),
        ]

    def clean(self):
        # Допущение 6 спецификации (S-DOM-02/03): специализированные
        # принтеры стоят только в основном цеху.
        if (self.specialization != SPEC_NONE and self.workshop_id
                and not self.workshop.is_main):
            raise ValidationError(
                'Специализированный принтер может находиться '
                'только в основном цеху.'
            )

    def __str__(self):
        return f'{self.name} ({self.workshop.name})'


class AuditLog(BaseModel):
    """Журнал изменений справочников (только вставка, S-SEC-07)."""

    ACTION_CHOICES = (
        ('CREATE', 'Создание'),
        ('UPDATE', 'Изменение'),
        ('DELETE', 'Удаление'),
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    entity_type = models.CharField(max_length=100)
    entity_id = models.UUIDField()
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)

    class Meta:
        verbose_name = 'Запись аудита'
        verbose_name_plural = 'Журнал изменений'
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['entity_type', 'entity_id'],
                name='catalog_audit_entity_idx',
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError('Записи аудита неизменяемы.')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Записи аудита неизменяемы.')

    def __str__(self):
        return f'{self.action} {self.entity_type} {self.entity_id}'
