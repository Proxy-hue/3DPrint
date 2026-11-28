import hashlib
import secrets
from uuid import uuid4

from django.db import models

from .contracts import ALL_SCOPES


API_KEY_PREFIX = "3dp_"


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    raw_key = f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"
    key_prefix = raw_key[:12]
    return raw_key, key_prefix, hash_api_key(raw_key)


class ApiClient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField("название клиента", max_length=150, unique=True)
    key_prefix = models.CharField("префикс ключа", max_length=16, editable=False)
    api_key_hash = models.CharField("хеш API-ключа", max_length=128, unique=True)
    scopes = models.JSONField("области доступа", default=list)
    is_active = models.BooleanField("активен", default=True)
    last_used_at = models.DateTimeField("последнее использование", null=True, blank=True)
    created_at = models.DateTimeField("создан", auto_now_add=True)
    updated_at = models.DateTimeField("обновлён", auto_now=True)

    class Meta:
        db_table = "api_client"
        ordering = ("name",)
        verbose_name = "интеграционный клиент"
        verbose_name_plural = "интеграционные клиенты"

    def __str__(self) -> str:
        return f"{self.name} ({self.key_prefix}…)"

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])

    @classmethod
    def normalize_scopes(cls, scopes: list[str] | tuple[str, ...]) -> list[str]:
        allowed = set(ALL_SCOPES)
        normalized: list[str] = []
        for scope in scopes:
            if scope not in allowed:
                raise ValueError(f"Недопустимая область доступа: {scope}")
            if scope not in normalized:
                normalized.append(scope)
        return normalized


class IntegrationOrderFacts(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    order = models.OneToOneField(
        "models.Order",
        on_delete=models.CASCADE,
        related_name="integration_facts",
        verbose_name="заказ",
    )
    actual_material_name = models.CharField(
        "фактический материал",
        max_length=150,
        blank=True,
        default="",
    )
    actual_material_g = models.DecimalField(
        "фактический расход материала, г",
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
    )
    actual_print_hours = models.DecimalField(
        "фактическое время печати, ч",
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
    )
    printer_name = models.CharField(
        "принтер",
        max_length=150,
        blank=True,
        default="",
    )
    notes = models.TextField("комментарий инженера", blank=True, default="")
    updated_by_client = models.ForeignKey(
        ApiClient,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_order_facts",
        verbose_name="интеграционный клиент",
    )
    created_at = models.DateTimeField("создано", auto_now_add=True)
    updated_at = models.DateTimeField("обновлено", auto_now=True)

    class Meta:
        db_table = "integration_order_facts"
        verbose_name = "фактические параметры печати"
        verbose_name_plural = "фактические параметры печати"

    def __str__(self) -> str:
        return f"Факты по заказу #{self.order_id}"


class IntegrationStatusEvent(models.Model):
    class EventType(models.TextChoices):
        STATUS_CHANGED = "STATUS_CHANGED", "Смена статуса"
        FACTS_RECORDED = "FACTS_RECORDED", "Фиксация фактических данных"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    order = models.ForeignKey(
        "models.Order",
        on_delete=models.CASCADE,
        related_name="integration_events",
        verbose_name="заказ",
    )
    actor_client = models.ForeignKey(
        ApiClient,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="status_events",
        verbose_name="интеграционный клиент",
    )
    event_type = models.CharField(
        "тип события",
        max_length=40,
        choices=EventType.choices,
        default=EventType.STATUS_CHANGED,
    )
    from_status = models.CharField("предыдущий статус", max_length=30, blank=True, default="")
    to_status = models.CharField("новый статус", max_length=30, blank=True, default="")
    reason = models.TextField("комментарий / причина", blank=True, default="")
    actual_data = models.JSONField("фактические данные", default=dict, blank=True)
    created_at = models.DateTimeField("создано", auto_now_add=True)

    class Meta:
        db_table = "integration_status_event"
        ordering = ("-created_at",)
        verbose_name = "событие интеграционного API"
        verbose_name_plural = "события интеграционного API"

    def __str__(self) -> str:
        return f"Заказ #{self.order_id}: {self.from_status} -> {self.to_status}"
