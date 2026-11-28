import csv
from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from orders.models import Order, OrderEvent, Status

from .contracts import (
    EngineeringStatusCommand,
    EngineeringStatusReceipt,
    ExportQuery,
    IssuedApiClient,
)
from .models import (
    ApiClient,
    IntegrationOrderFacts,
    IntegrationStatusEvent,
    generate_api_key,
)


ENGINEERING_VISIBLE_STATUSES: tuple[str, ...] = (
    Status.PAID,
    Status.DISTRIBUTED,
    Status.PRINTING,
    Status.POST_PROCESSING,
    Status.READY,
)
DAILY_PRINTER_WORK_HOURS = Decimal("20")
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class IntegrationServiceError(Exception):
    code = "INTEGRATION_ERROR"
    http_status = 400

    def __init__(self, message: str, *, code: str | None = None, http_status: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class IntegrationNotFoundError(IntegrationServiceError):
    code = "NOT_FOUND"
    http_status = 404


class InvalidStatusTransitionError(IntegrationServiceError):
    code = "INVALID_STATUS_TRANSITION"
    http_status = 409


def _has_post_processing(order: Order) -> bool:
    return order.post_processings.exists()


def _serialize_facts(facts: IntegrationOrderFacts | None) -> dict[str, Any]:
    if facts is None:
        return {
            "actual_material_name": None,
            "actual_material_g": None,
            "actual_print_hours": None,
            "printer_name": None,
            "notes": "",
            "updated_at": None,
        }
    return {
        "actual_material_name": facts.actual_material_name or None,
        "actual_material_g": (
            float(facts.actual_material_g) if facts.actual_material_g is not None else None
        ),
        "actual_print_hours": (
            float(facts.actual_print_hours) if facts.actual_print_hours is not None else None
        ),
        "printer_name": facts.printer_name or None,
        "notes": facts.notes,
        "updated_at": facts.updated_at.isoformat(),
    }


def _current_model_version(order: Order):
    if hasattr(order, "model_versions"):
        return order.model_versions.filter(is_current=True).first()
    return None


def _serialize_engineering_order(order: Order) -> dict[str, Any]:
    facts = getattr(order, "integration_facts", None)
    model_version = _current_model_version(order)
    model_payload = None
    if model_version is not None:
        model_payload = {
            "id": str(model_version.pk),
            "version": model_version.version,
            "file_name": model_version.file_name,
            "format": model_version.format,
            "size_bytes": model_version.size_bytes,
            "dimensions_mm": (
                {
                    "x": model_version.bbox_x,
                    "y": model_version.bbox_y,
                    "z": model_version.bbox_z,
                }
                if model_version.bbox_x is not None
                else None
            ),
            "volume_cm3": model_version.volume_cm3,
            "download_path": f"/api/integration/orders/{order.pk}/model/",
        }
    elif order.model_meta:
        model_payload = dict(order.model_meta)

    return {
        "id": str(order.pk),
        "number": order.number,
        "status": order.status,
        "priority": order.priority,
        "quantity": order.quantity,
        "technology": order.technology.code if order.technology else None,
        "material": order.material.name if order.material else None,
        "quality_profile": order.quality_profile.name if order.quality_profile else None,
        "color": order.color.name if order.color else None,
        "post_processing": list(order.post_processings.values_list("name", flat=True)),
        "has_post_processing": _has_post_processing(order),
        "model": model_payload,
        "actual_data": _serialize_facts(facts),
        "planned_date": order.planned_date.isoformat() if order.planned_date else None,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
    }


def issue_api_client(
    name: str,
    scopes: list[str] | tuple[str, ...],
    *,
    is_active: bool = True,
) -> IssuedApiClient:
    normalized_scopes = ApiClient.normalize_scopes(scopes)
    raw_key, key_prefix, key_hash = generate_api_key()
    client = ApiClient.objects.create(
        name=name,
        key_prefix=key_prefix,
        api_key_hash=key_hash,
        scopes=normalized_scopes,
        is_active=is_active,
    )
    return IssuedApiClient(
        client_id=client.pk,
        name=client.name,
        key_prefix=client.key_prefix,
        raw_api_key=raw_key,
        scopes=tuple(client.scopes),
        is_active=client.is_active,
    )


def rotate_api_client_key(client_id: UUID) -> IssuedApiClient:
    client = ApiClient.objects.filter(pk=client_id).first()
    if client is None:
        raise IntegrationNotFoundError("Интеграционный клиент не найден.")
    raw_key, key_prefix, key_hash = generate_api_key()
    client.key_prefix = key_prefix
    client.api_key_hash = key_hash
    client.save(update_fields=("key_prefix", "api_key_hash", "updated_at"))
    return IssuedApiClient(
        client_id=client.pk,
        name=client.name,
        key_prefix=client.key_prefix,
        raw_api_key=raw_key,
        scopes=tuple(client.scopes),
        is_active=client.is_active,
    )


def revoke_api_client(client_id: UUID) -> ApiClient:
    client = ApiClient.objects.filter(pk=client_id).first()
    if client is None:
        raise IntegrationNotFoundError("Интеграционный клиент не найден.")
    if client.is_active:
        client.is_active = False
        client.save(update_fields=("is_active", "updated_at"))
    return client


def _engineering_orders_queryset() -> QuerySet[Order]:
    return (
        Order.objects.select_related(
            "technology",
            "material",
            "quality_profile",
            "color",
            "integration_facts",
        )
        .prefetch_related("post_processings", "model_versions")
        .filter(status__in=ENGINEERING_VISIBLE_STATUSES)
        .order_by("created_at", "id")
    )


def list_engineering_orders(*, status_filter: str | None = None) -> list[dict[str, Any]]:
    queryset = _engineering_orders_queryset()
    if status_filter:
        normalized = status_filter.strip()
        if normalized not in ENGINEERING_VISIBLE_STATUSES:
            raise IntegrationServiceError(
                "Допустимы только статусы инженерного контура (PAID…READY).",
                code="INVALID_STATUS_FILTER",
                http_status=400,
            )
        queryset = queryset.filter(status=normalized)
    return [_serialize_engineering_order(order) for order in queryset]


def get_engineering_order_with_model(order_id: UUID) -> tuple[Order, Any]:
    order = _engineering_orders_queryset().filter(pk=order_id).first()
    if order is None:
        raise IntegrationNotFoundError(
            "Заказ не найден в инженерном контуре (ожидаются статусы PAID…READY)."
        )
    model_version = _current_model_version(order)
    if model_version is None:
        raise IntegrationNotFoundError("Файл 3D-модели не прикреплён к заказу.")
    return order, model_version


def _validate_engineering_transition(
    current_status: str,
    target_status: str,
    *,
    has_post_processing: bool,
) -> None:
    if current_status not in ENGINEERING_VISIBLE_STATUSES:
        raise InvalidStatusTransitionError(
            f"Заказ в статусе '{current_status}' недоступен для инженерного модуля."
        )

    if target_status == current_status:
        return

    if current_status == Status.DISTRIBUTED and target_status == Status.PRINTING:
        return

    if current_status == Status.PRINTING:
        if target_status == Status.POST_PROCESSING:
            if not has_post_processing:
                raise InvalidStatusTransitionError(
                    "Переход в POST_PROCESSING невозможен: в заказе не выбрана постобработка."
                )
            return
        if target_status == Status.READY:
            if has_post_processing:
                raise InvalidStatusTransitionError(
                    "Переход сразу в READY невозможен: в заказе выбрана постобработка."
                )
            return

    raise InvalidStatusTransitionError(
        f"Недопустимый переход статуса для инженерного модуля: '{current_status}' -> '{target_status}'."
    )


def _apply_actual_facts(
    order: Order,
    command: EngineeringStatusCommand,
    client: ApiClient | None,
) -> tuple[dict[str, Any], bool]:
    has_updates = any(
        value is not None
        for value in (
            command.actual_material_name,
            command.actual_material_g,
            command.actual_print_hours,
            command.printer_name,
            command.notes,
        )
    )
    facts = IntegrationOrderFacts.objects.filter(order=order).first()
    if not has_updates:
        return _serialize_facts(facts), False

    if facts is None:
        facts = IntegrationOrderFacts(order=order)
    if command.actual_material_name is not None:
        facts.actual_material_name = command.actual_material_name.strip()
    if command.actual_material_g is not None:
        facts.actual_material_g = command.actual_material_g
    if command.actual_print_hours is not None:
        facts.actual_print_hours = command.actual_print_hours
    if command.printer_name is not None:
        facts.printer_name = command.printer_name.strip()
    if command.notes is not None:
        facts.notes = command.notes
    facts.updated_by_client = client
    facts.save()
    return _serialize_facts(facts), True


@transaction.atomic
def update_engineering_order_status(
    command: EngineeringStatusCommand,
) -> EngineeringStatusReceipt:
    order = (
        Order.objects.select_for_update()
        .filter(pk=command.order_id)
        .first()
    )
    if order is None:
        raise IntegrationNotFoundError(f"Заказ {command.order_id} не найден.")

    previous_status = order.status
    if previous_status not in ENGINEERING_VISIBLE_STATUSES:
        raise InvalidStatusTransitionError(
            f"Заказ в статусе '{previous_status}' недоступен для инженерного модуля."
        )

    target_status = command.target_status
    if target_status is not None:
        _validate_engineering_transition(
            previous_status,
            target_status,
            has_post_processing=_has_post_processing(order),
        )
        new_status = target_status
    else:
        new_status = previous_status

    client = ApiClient.objects.filter(pk=command.actor_client_id).first()
    actual_data, facts_updated = _apply_actual_facts(order, command, client)

    status_changed = new_status != previous_status
    if status_changed:
        order.status = new_status
        order.save(update_fields=("status", "updated_at"))
        OrderEvent.objects.create(
            order=order,
            actor=None,
            type="INTEGRATION_STATUS_CHANGED",
            from_status=previous_status,
            to_status=new_status,
            reason=command.reason,
            payload={
                "integration_client": client.name if client else None,
                "actual_data": actual_data if facts_updated else {},
            },
        )
    else:
        order.refresh_from_db(fields=("updated_at",))

    event: IntegrationStatusEvent | None = None
    if status_changed or facts_updated:
        event_type = (
            IntegrationStatusEvent.EventType.STATUS_CHANGED
            if status_changed
            else IntegrationStatusEvent.EventType.FACTS_RECORDED
        )
        event = IntegrationStatusEvent.objects.create(
            order=order,
            actor_client=client,
            event_type=event_type,
            from_status=previous_status,
            to_status=order.status,
            reason=command.reason,
            actual_data=actual_data if facts_updated else {},
        )
    elif target_status is None:
        raise IntegrationServiceError(
            "Укажите новый статус или хотя бы одно фактическое поле.",
            code="EMPTY_UPDATE",
            http_status=400,
        )

    return EngineeringStatusReceipt(
        order_id=order.pk,
        order_number=order.number,
        previous_status=previous_status,
        status=order.status,
        actual_data=actual_data,
        event_id=event.pk if event is not None else None,
        updated_at=order.updated_at,
    )


def _apply_date_range(queryset: QuerySet, query: ExportQuery, field: str = "created_at") -> QuerySet:
    tz = timezone.get_current_timezone()
    if query.date_from is not None:
        start_dt = timezone.make_aware(datetime.combine(query.date_from, time.min), tz)
        queryset = queryset.filter(**{f"{field}__gte": start_dt})
    if query.date_to is not None:
        end_dt = timezone.make_aware(datetime.combine(query.date_to, time.max), tz)
        queryset = queryset.filter(**{f"{field}__lte": end_dt})
    return queryset


def export_orders(query: ExportQuery) -> list[dict[str, Any]]:
    queryset = (
        Order.objects.select_related(
            "client",
            "technology",
            "material",
            "quality_profile",
            "color",
            "integration_facts",
        )
        .prefetch_related("quotes")
        .order_by("-created_at", "-id")
    )
    if query.status:
        queryset = queryset.filter(status=query.status)
    queryset = _apply_date_range(queryset, query)

    rows: list[dict[str, Any]] = []
    for order in queryset:
        facts = getattr(order, "integration_facts", None)
        quote = order.quotes.filter(is_current=True).first()
        rows.append(
            {
                "order_id": str(order.pk),
                "number": order.number,
                "status": order.status,
                "client_id": str(order.client_id),
                "technology": order.technology.code if order.technology else "",
                "material": order.material.name if order.material else "",
                "quality_profile": order.quality_profile.name if order.quality_profile else "",
                "quantity": order.quantity,
                "total_price": float(quote.total) if quote else None,
                "estimated_days": quote.estimated_days if quote else None,
                "planned_print_hours": float(quote.print_hours) if quote else None,
                "printer_name": facts.printer_name if facts else "",
                "actual_material_name": facts.actual_material_name if facts else "",
                "actual_material_g": (
                    float(facts.actual_material_g)
                    if facts and facts.actual_material_g is not None
                    else None
                ),
                "actual_print_hours": (
                    float(facts.actual_print_hours)
                    if facts and facts.actual_print_hours is not None
                    else None
                ),
                "created_at": order.created_at.isoformat(),
                "updated_at": order.updated_at.isoformat(),
            }
        )
    return rows


def export_events(query: ExportQuery) -> list[dict[str, Any]]:
    queryset = OrderEvent.objects.select_related("order", "actor").order_by("-created_at")
    if query.order_id is not None:
        queryset = queryset.filter(order_id=query.order_id)
    queryset = _apply_date_range(queryset, query)

    return [
        {
            "event_id": str(event.pk),
            "order_id": str(event.order_id),
            "order_number": event.order.number,
            "actor_email": event.actor.email if event.actor else None,
            "event_type": event.type,
            "from_status": event.from_status,
            "to_status": event.to_status,
            "reason": event.reason,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
        for event in queryset
    ]


def export_load(query: ExportQuery) -> list[dict[str, Any]]:
    horizon_days = max(1, min(query.horizon_days, 90))
    now = timezone.now()
    since = now - timedelta(days=horizon_days)
    capacity_hours = float(DAILY_PRINTER_WORK_HOURS * horizon_days)

    queryset = (
        Order.objects.select_related("technology", "integration_facts")
        .prefetch_related("quotes", "assignments__printer")
        .filter(created_at__gte=since)
        .order_by("created_at")
    )

    buckets: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {
            "orders_count": 0,
            "active_orders_count": 0,
            "completed_orders_count": 0,
            "planned_hours": 0.0,
            "actual_print_hours": 0.0,
            "actual_material_g": 0.0,
        }
    )

    for order in queryset:
        facts = getattr(order, "integration_facts", None)
        assignment = order.assignments.filter(is_current=True).first()
        if facts and facts.printer_name:
            printer_name = facts.printer_name
        elif assignment is not None:
            printer_name = assignment.printer.name
        else:
            printer_name = "unassigned"
        technology = order.technology.code if order.technology else "UNKNOWN"

        bucket = buckets[(printer_name, technology)]
        bucket["orders_count"] += 1
        if order.status in ENGINEERING_VISIBLE_STATUSES:
            bucket["active_orders_count"] += 1
        elif order.status == Status.COMPLETED:
            bucket["completed_orders_count"] += 1

        quote = order.quotes.filter(is_current=True).first()
        if quote is not None:
            bucket["planned_hours"] += float(quote.print_hours)

        if facts is not None:
            if facts.actual_print_hours is not None:
                bucket["actual_print_hours"] += float(facts.actual_print_hours)
            if facts.actual_material_g is not None:
                bucket["actual_material_g"] += float(facts.actual_material_g)

    rows: list[dict[str, Any]] = []
    for (printer_name, technology), stats in sorted(buckets.items()):
        actual_hours = round(stats["actual_print_hours"], 3)
        planned_hours = round(stats["planned_hours"], 3)
        utilized = actual_hours if actual_hours > 0 else planned_hours
        load_percent = round(min(100.0, (utilized / capacity_hours) * 100.0), 2) if capacity_hours else 0.0
        rows.append(
            {
                "printer_name": printer_name,
                "technology": technology,
                "horizon_days": horizon_days,
                "capacity_hours": capacity_hours,
                "orders_count": stats["orders_count"],
                "active_orders_count": stats["active_orders_count"],
                "completed_orders_count": stats["completed_orders_count"],
                "planned_hours": planned_hours,
                "actual_print_hours": actual_hours,
                "actual_material_g": round(stats["actual_material_g"], 3),
                "load_percent": load_percent,
                "idle_hours": round(max(0.0, capacity_hours - utilized), 3),
            }
        )
    return rows


def _sanitize_csv_cell(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if text.startswith(CSV_FORMULA_PREFIXES):
        return f"'{text}"
    return text


def render_csv(rows: list[dict[str, Any]], columns: tuple[str, ...]) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([_sanitize_csv_cell(row.get(col)) for col in columns])
    return buffer.getvalue()
