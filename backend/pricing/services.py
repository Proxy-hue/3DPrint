"""Публичный интерфейс расчёта стоимости и сроков (спец. 6.3).

Берёт параметры тарифов из catalog.services и при наличии модуля scheduling
учитывает время ожидания очереди W.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction

from catalog import services as catalog_services
from orders.exceptions import DomainError

from .formulas import compute_quote, round_half_up
from .models import Quote


class QuoteError(DomainError):
    def __init__(self, message, code='no_quote', status=400):
        super().__init__(message, code=code, status=status)


def get_tariff_params() -> dict:
    return catalog_services.get_tariff_params()


def get_active_tariff():
    return catalog_services.get_active_tariff_version()


def current_quote(order):
    if hasattr(order, '_prefetched_objects_cache') and 'quotes' in order._prefetched_objects_cache:
        for q in order._prefetched_objects_cache['quotes']:
            if q.is_current:
                return q
        return None
    return Quote.objects.filter(order=order, is_current=True).first()


def _parse_decimal(val) -> Decimal:
    try:
        d = Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        raise DomainError('Некорректное числовое значение корректировки.', 'validation', 400)
    if not d.is_finite():
        raise DomainError('Некорректное числовое значение корректировки.', 'validation', 400)
    return d.quantize(Decimal('0.01'))


def _extract_geometry(mv):
    if mv is None:
        return None, [0, 0, 0]
    if isinstance(mv, dict):
        vol = mv.get('volume_cm3')
        bbox = mv.get('bbox') or [mv.get('bbox_x') or 0, mv.get('bbox_y') or 0, mv.get('bbox_z') or 0]
        return vol, bbox
    return getattr(mv, 'volume_cm3', None), [
        getattr(mv, 'bbox_x', 0) or 0,
        getattr(mv, 'bbox_y', 0) or 0,
        getattr(mv, 'bbox_z', 0) or 0,
    ]


def _queue_wait_hours(*, technology, material, color, bbox) -> float:
    try:
        from scheduling import services as scheduling_services
    except ImportError:
        return 0.0
    fn = getattr(scheduling_services, 'queue_wait_hours', None)
    if not callable(fn):
        return 0.0
    return float(fn(technology=technology, material=material, color=color, bbox=bbox))


@transaction.atomic
def calculate(
    order, mv=None, *, volume_cm3=None, bbox=None,
    needs_support=False, adjustment=None, queue_wait_h=None,
):
    """Считает и сохраняет Quote. Бросает QuoteError, если не хватает параметров."""
    if not (order.technology and order.material and order.quality_profile and order.delivery_method):
        raise QuoteError('Заполнены не все параметры заказа.')

    mv_vol, mv_bbox = _extract_geometry(mv)
    vol = mv_vol if volume_cm3 is None else volume_cm3
    box = mv_bbox if bbox is None else bbox
    if not vol or float(vol) <= 0:
        raise QuoteError('Объём модели не определён.')

    tariff = get_active_tariff()
    params = get_tariff_params()
    prev = Quote.objects.select_for_update().filter(order=order, is_current=True).first()
    adj_dec = _parse_decimal(adjustment) if adjustment is not None else (
        prev.adjustment if prev else Decimal('0.00')
    )
    pps = list(order.post_processings.all())
    wait = (
        float(queue_wait_h) if queue_wait_h is not None
        else _queue_wait_hours(technology=order.technology, material=order.material, color=order.color, bbox=box)
    )

    tech, q, mat, dm = order.technology, order.quality_profile, order.material, order.delivery_method
    c_min = params.get('min_cost', params.get('min_order_cost', 300))
    printer_h = params.get('printer_hours_per_day', 20)
    post_h = params.get('postprocessing_hours_per_day', params.get('post_hours_per_day', 8))

    r = compute_quote(
        volume_cm3=vol, quantity=order.quantity, needs_support=needs_support,
        density=mat.density, price_per_gram=mat.price_per_gram, fill_factor=tech.fill_factor,
        support_factor=tech.support_factor, flow_cm3_h=q.flow_cm3_h, hourly_rate=tech.hourly_rate,
        setup_cost=tech.setup_cost, price_factor=q.price_factor,
        post_prices=[p.price for p in pps], post_hours=[p.hours for p in pps],
        delivery_price=dm.price, delivery_days=dm.days, adjustment=adj_dec, queue_wait_h=wait,
        c_min=c_min, printer_hours_per_day=printer_h, post_hours_per_day=post_h,
    )
    if r.total < 0:
        raise DomainError('Итоговая стоимость заказа не может быть отрицательной.', 'validation', 400)

    Quote.objects.filter(order=order, is_current=True).update(is_current=False)
    return Quote.objects.create(
        order=order, tariff_version=tariff,
        cost_material=round(r.cost_material, 2), cost_machine=round(r.cost_machine, 2),
        cost_post=round(r.cost_post, 2), cost_delivery=round(r.cost_delivery, 2),
        adjustment=adj_dec, total=r.total,
        print_hours=round(r.print_hours, 2), mass_g=round(r.mass_g, 2),
        estimated_days=r.estimated_days, is_current=True,
    )


@transaction.atomic
def apply_adjustment(order, adjustment):
    """Корректировка цены администратором с проверкой неотрицательного итога и блокировкой."""
    adj_dec = _parse_decimal(adjustment)
    q = Quote.objects.select_for_update().filter(order=order, is_current=True).first()
    if not q:
        raise QuoteError('Расчёт отсутствует.', 'no_quote', 409)
    old_adj = q.adjustment
    new_total = round_half_up(float(Decimal(q.total) - old_adj + adj_dec))
    if new_total < 0:
        raise DomainError('Итоговая стоимость заказа не может быть отрицательной.', 'validation', 400)
    Quote.objects.filter(order=order, is_current=True).update(is_current=False)
    return Quote.objects.create(
        order=order, tariff_version=q.tariff_version,
        cost_material=q.cost_material, cost_machine=q.cost_machine,
        cost_post=q.cost_post, cost_delivery=q.cost_delivery,
        adjustment=adj_dec, total=new_total,
        print_hours=q.print_hours, mass_g=q.mass_g,
        estimated_days=q.estimated_days, is_current=True,
    )
