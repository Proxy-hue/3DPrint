"""Чистые формулы цены и сроков (спецификация, раздел 6.3). Без зависимостей от Django."""
import math
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

C_MIN_DEFAULT = 300
PRINTER_HOURS_PER_DAY = 20
POST_HOURS_PER_DAY = 8


def _f(x):
    return float(x)


@dataclass
class QuoteResult:
    mass_g: float
    print_hours: float
    cost_material: float
    cost_machine: float
    cost_base: float
    cost_post: float
    cost_delivery: float
    adjustment: float
    total: int
    days_print: int
    days_post: int
    days_delivery: int
    estimated_days: int


def round_half_up(x: float) -> int:
    return int(Decimal(repr(round(x, 9))).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def compute_quote(
    *, volume_cm3, quantity, needs_support, density, price_per_gram,
    fill_factor, support_factor, flow_cm3_h, hourly_rate, setup_cost,
    price_factor, post_prices=(), post_hours=(), delivery_price=0,
    delivery_days=0, adjustment=0, queue_wait_h=0.0,
    c_min=C_MIN_DEFAULT, printer_hours_per_day=PRINTER_HOURS_PER_DAY,
    post_hours_per_day=POST_HOURS_PER_DAY,
) -> QuoteResult:
    V, N = _f(volume_cm3), int(quantity)
    s = 1 if needs_support else 0
    eff = N * V * _f(fill_factor) * (1 + _f(support_factor) * s)
    m = eff * _f(density)
    t = eff / _f(flow_cm3_h)
    c_mat = m * _f(price_per_gram)
    c_mach = t * _f(hourly_rate)
    c_base = (c_mat + c_mach + _f(setup_cost)) * _f(price_factor)
    c_post = N * sum(_f(p) for p in post_prices)
    total = round_half_up(max(_f(c_min), c_base + c_post) + _f(delivery_price) + _f(adjustment))
    d_print = math.ceil(round((_f(queue_wait_h) + t) / printer_hours_per_day, 9))
    d_post = math.ceil(round((N * sum(_f(h) for h in post_hours)) / post_hours_per_day, 9))
    d_del = int(delivery_days)
    return QuoteResult(
        m, t, c_mat, c_mach, c_base, c_post, _f(delivery_price), _f(adjustment),
        total, d_print, d_post, d_del, d_print + d_post + d_del,
    )
