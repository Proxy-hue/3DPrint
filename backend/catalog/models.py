import uuid
from django.db import models
from django.core.validators import MinValueValidator


class Workshop(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Название цеха"
    )
    address = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Адрес"
    )
    is_main = models.BooleanField(
        default=False,
        verbose_name="Основной цех"
    )

    class Meta:
        verbose_name = "Цех"
        verbose_name_plural = "Цеха"

    def __str__(self):
        return self.name


class Technology(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Код (FDM, SLA, DMLS)")
    name = models.CharField(
        max_length=100,
        verbose_name="Название"
    )
    fill_factor = models.FloatField(
        default=1.0,
        verbose_name="Коэффициент заполнения"
    )
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0.0,
        verbose_name="Стоимость часа (₽)"
    )

    class Meta:
        verbose_name = "Технология"
        verbose_name_plural = "Технологии"

    def __str__(self):
        return f"{self.code} - {self.name}"


class QualityProfile(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    technology = models.ForeignKey(
        Technology,
        on_delete=models.CASCADE,
        related_name='quality_profiles',
        verbose_name="Технология"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Название профиля"
    )
    layer_height = models.FloatField(
        verbose_name="Толщина слоя (мм)"
    )
    flow_rate = models.FloatField(
        verbose_name="Поток печати (см³/ч)"
    )

    class Meta:
        verbose_name = "Профиль качества"
        verbose_name_plural = "Профили качества"

    def __str__(self):
        return f"{self.technology.code} - {self.name}"


class Material(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Название материала"
    )
    density = models.FloatField(
        validators=[MinValueValidator(0.1)],
        verbose_name="Плотность (г/см³)"
    )
    price_per_gram = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.01)],
        verbose_name="Цена за грамм (₽)"
    )
    technology = models.ForeignKey(
        Technology,
        on_delete=models.CASCADE,
        related_name='materials',
        verbose_name="Технология"
    )

    class Meta:
        verbose_name = "Материал"
        verbose_name_plural = "Материалы"

    def __str__(self):
        return f"{self.name} ({self.technology.code})"


class Color(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(
        max_length=50,
        verbose_name="Название цвета"
    )
    hex_code = models.CharField(
        max_length=7,
        blank=True,
        verbose_name="HEX-код"
    )

    class Meta:
        verbose_name = "Цвет"
        verbose_name_plural = "Цвета"

    def __str__(self):
        return self.name


class Printer(models.Model):

    STATUS_CHOICES = (
        ('ACTIVE', 'В работе'),
        ('MAINTENANCE', 'Обслуживание'),
        ('RETIRED', 'Списан'),
    )
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Название принтера"
    )
    workshop = models.ForeignKey(
        Workshop,
        on_delete=models.CASCADE,
        related_name='printers',
        verbose_name="Цех"
    )
    technology = models.ForeignKey(
        Technology,
        on_delete=models.CASCADE,
        verbose_name="Технология"
    )

    max_x = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Макс. X (мм)"
    )
    max_y = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Макс. Y (мм)"
    )
    max_z = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name="Макс. Z (мм)"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE',
        verbose_name="Статус"
    )

    class Meta:
        verbose_name = "Принтер"
        verbose_name_plural = "Принтеры"

    def __str__(self):
        return f"{self.name} ({self.workshop.name})"
