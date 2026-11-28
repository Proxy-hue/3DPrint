"""Публичный интерфейс модуля scheduling (слой services).

Функции ниже вызываются из ``orders.adapters`` и ``pricing.services``
(контракт описан в ``orders/README.md``):

* ``queue_wait_hours``  — время ожидания очереди W для расчёта срока;
* ``recommend``         — рекомендация принтеров (топ-3 и остальные);
* ``get_printer``       — принтер по идентификатору;
* ``assign``            — назначение заказа на принтер;
* ``current_assignment`` / ``clear_assignment`` — текущее назначение.

Данные каталога берутся только из ``catalog.services``.
"""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from catalog import services as catalog_services
from catalog.models import Printer

from . import engine
from .engine import OrderRequirements, PlannedJob, PrinterQueue
from .models import Assignment

TOP_SIZE = 3


class AssignmentError(Exception):
    """Назначение невозможно. ``code`` — машинно-читаемая причина."""

    def __init__(self, code, details=None):
        super().__init__(code)
        self.code = code
        self.details = details or []


def _requirements(*, technology, material, color, bbox, print_hours):
    return OrderRequirements(
        technology_id=str(technology.pk),
        material=catalog_services.get_material_spec(material.pk),
        color_id=str(color.pk) if color is not None else None,
        dims_mm=tuple(float(x or 0) for x in bbox),
        print_hours=float(print_hours or 0.0),
    )


def _queues(now, exclude_order_pk=None):
    """Плановые очереди принтеров по текущим назначениям."""
    state = {}
    assignments = Assignment.objects.filter(is_current=True)
    if exclude_order_pk is not None:
        assignments = assignments.exclude(order_id=exclude_order_pk)
    for item in assignments.order_by('planned_end'):
        entry = state.setdefault(
            str(item.printer_id), {'hours': 0.0, 'last': None}
        )
        if item.planned_end > now:
            entry['hours'] += item.planned_hours
        if item.material_id is not None:
            entry['last'] = str(item.material_id)
    return {
        printer_id: PrinterQueue(
            queue_hours=entry['hours'], last_material_id=entry['last']
        )
        for printer_id, entry in state.items()
    }


def _run(req, *, now, exclude_order_pk=None):
    printers = catalog_services.get_printer_specs(include_inactive=True)
    result = engine.recommend(
        req, printers, _queues(now, exclude_order_pk), now,
        catalog_services.get_tariff_params(), limit=TOP_SIZE,
    )
    return result, printers


# --- Контракт с pricing ---

def queue_wait_hours(*, technology, material, color, bbox, now=None):
    """W: ожидание очереди наименее загруженного подходящего принтера, ч.

    Если подходящих принтеров нет, возвращает 0 (ошибку E-06 покажет
    проверка модели, а не расчёт цены).
    """
    now = now or timezone.now()
    req = _requirements(
        technology=technology, material=material, color=color,
        bbox=bbox, print_hours=0.0,
    )
    result, _ = _run(req, now=now)
    if not result.candidates:
        return 0.0
    return float(min(c.queue_hours for c in result.candidates))


# --- Контракт с orders ---

def _item(rec, required):
    printer = rec.printer
    return {
        'printer_id': printer.id,
        'printer': printer.name,
        'workshop_id': printer.workshop_id,
        'workshop': printer.workshop_name,
        'specialization': printer.specialization,
        'score': round(rec.score, 2),
        'queue_hours': round(rec.queue_hours, 2),
        'planned_start': rec.planned_start,
        'planned_end': rec.planned_end,
        'reserve': engine.is_reserve(printer, required),
    }


def recommend(*, technology, material, color, bbox, print_hours,
              exclude_order=None, now=None):
    """Рекомендация принтеров (GET /api/orders/{id}/recommendation).

    Возвращает ``{'top': [...], 'others': [...], ...}``: в ``top`` три
    лучших принтера по Score, в ``others`` остальные подходящие. Если
    подходящих нет, оба списка пусты, ``error_code == 'E-06'``, а в
    ``excluded`` указано, почему отсеян каждый принтер.
    """
    now = now or timezone.now()
    req = _requirements(
        technology=technology, material=material, color=color,
        bbox=bbox, print_hours=print_hours,
    )
    result, printers = _run(
        req, now=now,
        exclude_order_pk=(
            exclude_order.pk if exclude_order is not None else None
        ),
    )
    required = result.required_specialization
    items = [_item(rec, required) for rec in result.candidates]
    names = {p.id: p.name for p in printers}
    return {
        'top': items[:TOP_SIZE],
        'others': items[TOP_SIZE:],
        'required_specialization': required,
        'error_code': result.error_code,
        'excluded': [
            {'printer_id': pid, 'printer': names.get(pid, ''),
             'reasons': reasons}
            for pid, reasons in result.excluded.items()
        ],
    }


def get_printer(printer_id):
    return Printer.objects.select_related('workshop').get(pk=printer_id)


def current_assignment(order):
    return Assignment.objects.select_related(
        'printer__workshop'
    ).filter(order=order, is_current=True).first()


def clear_assignment(order):
    """Снять текущее назначение (отмена или отклонение заказа)."""
    Assignment.objects.filter(order=order, is_current=True).update(
        is_current=False
    )


@transaction.atomic
def assign(*, order, printer, print_hours, actor_reason='',
           is_manual=False, now=None):
    """Назначить заказ на принтер (POST /api/orders/{id}/assignment).

    Допустимость принтера и причину ручного выбора проверяет orders до
    вызова. Плановые даты считаются по очереди принтера без учёта
    прежнего назначения этого же заказа, которое снимается.
    """
    now = now or timezone.now()
    params = catalog_services.get_tariff_params()
    queue = _queues(now, order.pk).get(str(printer.pk), PrinterQueue())
    hours = float(print_hours or 0.0)
    start = now + engine.working_hours_to_timedelta(queue.queue_hours, params)
    end = start + engine.working_hours_to_timedelta(hours, params)

    clear_assignment(order)
    return Assignment.objects.create(
        order=order,
        printer=printer,
        material_id=order.material_id,
        planned_start=start,
        planned_end=end,
        planned_hours=hours,
        is_manual=bool(is_manual),
        reason=(actor_reason or '').strip()[:500],
    )


def auto_assign(*, order, technology, material, color, bbox, print_hours,
                now=None):
    """Назначение на лучший принтер без участия менеджера (цель 3.8)."""
    now = now or timezone.now()
    rec = recommend(
        technology=technology, material=material, color=color, bbox=bbox,
        print_hours=print_hours, exclude_order=order, now=now,
    )
    if not rec['top']:
        raise AssignmentError(engine.NO_PRINTER_CODE, rec['excluded'])
    printer = get_printer(rec['top'][0]['printer_id'])
    return assign(
        order=order, printer=printer, print_hours=print_hours,
        is_manual=False, now=now,
    )


# --- Загрузка оборудования ---

def get_load(*, now=None):
    """Плановая загрузка принтеров и цехов (GET /api/load/)."""
    now = now or timezone.now()
    params = catalog_services.get_tariff_params()
    printers = catalog_services.get_printer_specs()
    horizon_end = now + timedelta(days=params['load_horizon_days'])
    jobs = [
        PlannedJob(
            printer_id=str(a.printer_id), start=a.planned_start,
            end=a.planned_end, hours=a.planned_hours,
        )
        for a in Assignment.objects.filter(
            is_current=True, planned_end__gt=now,
            planned_start__lt=horizon_end,
        )
    ]
    printer_loads, workshop_loads, capacity = engine.compute_load(
        printers, jobs, now, params
    )
    return {
        'horizon_days': params['load_horizon_days'],
        'capacity_hours': capacity,
        'printers': printer_loads,
        'workshops': workshop_loads,
    }
