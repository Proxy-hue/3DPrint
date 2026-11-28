"""Тесты расчёта стоимости и сроков (Приложение В: T-01..T-24, корректировки, интеграция с catalog)."""
import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.core.management import call_command

from catalog.models import (
    Color, DeliveryMethod, Material, PickupPoint, PostProcessing, QualityProfile,
    Technology,
)
from orders.exceptions import DomainError
from orders.models import Order
from pricing import services as pricing_services
from pricing.formulas import compute_quote
from pricing.models import Quote
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog_data():
    call_command('loaddata', 'initial_catalog', verbosity=0)


@pytest.fixture
def client_user():
    return User.objects.create_user(email='pricing_client@test.local', password='pass12345', role='CLIENT')


def _make_order_for_pricing(
    user, *, tech, material, quality, color, volume, bbox=(50, 50, 20),
    qty=1, pp=(), delivery='PICKUP',
):
    t = Technology.objects.get(code=tech)
    m = Material.objects.get(name=material)
    q = QualityProfile.objects.get(technology=t, name=quality)
    c = Color.objects.get(name=color)
    dm = DeliveryMethod.objects.get(type=delivery)
    pickup = PickupPoint.objects.filter(delivery_method=dm).first() if delivery == 'PICKUP' else None
    o = Order.objects.create(
        client=user,
        number=f'TEST-{uuid.uuid4().hex[:8].upper()}',
        status='DRAFT',
        technology=t,
        material=m,
        quality_profile=q,
        color=c,
        delivery_method=dm,
        pickup_point=pickup,
        quantity=qty,
    )
    for name in pp:
        o.post_processings.add(PostProcessing.objects.get(name=name))
    mv = SimpleNamespace(
        volume_cm3=volume,
        bbox_x=bbox[0],
        bbox_y=bbox[1],
        bbox_z=bbox[2],
    )
    return o, mv


CASES = [
    ('T-01', dict(tech='FDM', material='PLA', quality='Стандартное', color='белый',
                  bbox=(60, 40, 20), volume=18, qty=1, needs_support=False), 300, 1),
    ('T-02', dict(tech='FDM', material='ABS', quality='Стандартное', color='белый',
                  bbox=(90, 60, 35), volume=55, qty=2, pp=['Шлифовка'], delivery='COURIER',
                  needs_support=False), 1748, 4),
    ('T-03', dict(tech='FDM', material='Нейлон (PA12)', quality='Высокое', color='белый',
                  bbox=(50, 50, 12), volume=14, qty=4, needs_support=False), 726, 1),
    ('T-04', dict(tech='FDM', material='PLA', quality='Черновое', color='белый',
                  bbox=(110, 80, 70), volume=60, qty=1, needs_support=True), 320, 1),
    ('T-05', dict(tech='FDM', material='PLA', quality='Стандартное', color='белый',
                  bbox=(120, 80, 15), volume=40, qty=3, pp=['Покраска'], delivery='COURIER',
                  needs_support=False), 3392, 6),
    ('T-06', dict(tech='FDM', material='ABS', quality='Стандартное', color='белый',
                  bbox=(45, 30, 25), volume=9, qty=10, needs_support=False), 517, 1),
    ('T-07', dict(tech='FDM', material='PLA', quality='Высокое', color='белый',
                  bbox=(150, 70, 40), volume=85, qty=1, pp=['Шлифовка', 'Покраска'],
                  delivery='COURIER', needs_support=False), 2475, 4),
    ('T-08', dict(tech='FDM', material='PLA', quality='Черновое', color='белый',
                  bbox=(200, 200, 100), volume=210, qty=1, needs_support=True), 783, 1),
    ('T-09', dict(tech='FDM', material='ABS', quality='Стандартное', color='белый',
                  bbox=(35, 35, 110), volume=48, qty=2, pp=['Шлифовка'], needs_support=False), 1341, 2),
    ('T-10', dict(tech='FDM', material='PLA', quality='Стандартное', color='белый',
                  bbox=(80, 50, 6), volume=12, qty=6, delivery='COURIER', needs_support=False), 795, 3),
    ('T-11', dict(tech='FDM', material='PLA', quality='Стандартное', color='белый',
                  bbox=(100, 100, 60), volume=70, qty=1, pp=['Сборка'], needs_support=False), 1037, 2),
    ('T-12', dict(tech='FDM', material='ABS', quality='Стандартное', color='белый',
                  bbox=(180, 180, 200), volume=150, qty=1, pp=['Шлифовка', 'Покраска'],
                  delivery='COURIER', needs_support=True), 2403, 4),
    ('T-13', dict(tech='FDM', material='PLA', quality='Стандартное', color='белый',
                  bbox=(400, 300, 60), volume=320, qty=1, needs_support=False), 1463, 1),
    ('T-14', dict(tech='FDM', material='ABS', quality='Черновое', color='белый',
                  bbox=(450, 200, 150), volume=380, qty=1, pp=['Шлифовка'], needs_support=True), 1697, 2),
    ('T-15', dict(tech='SLA', material='Стандартная смола', quality='Высокое', color='серый',
                  bbox=(40, 30, 50), volume=12, qty=3, pp=['Покраска'], needs_support=False), 3490, 4),
    ('T-16', dict(tech='SLA', material='Стандартная смола', quality='Высокое', color='серый',
                  bbox=(25, 25, 10), volume=2, qty=5, delivery='COURIER', needs_support=False), 879, 3),
    ('T-17', dict(tech='SLA', material='Стандартная смола', quality='Стандартное', color='серый',
                  bbox=(60, 50, 30), volume=15, qty=2, needs_support=False), 588, 1),
    ('T-18', dict(tech='SLA', material='Стандартная смола', quality='Стандартное', color='серый',
                  bbox=(120, 90, 40), volume=50, qty=1, pp=['Шлифовка'], delivery='COURIER',
                  needs_support=False), 1564, 4),
    ('T-19', dict(tech='SLA', material='Высокопрочная смола', quality='Стандартное', color='серый',
                  bbox=(100, 60, 25), volume=30, qty=2, needs_support=False), 1231, 1),
    ('T-20', dict(tech='SLA', material='Высокопрочная смола', quality='Высокое', color='серый',
                  bbox=(70, 40, 40), volume=25, qty=4, delivery='COURIER', needs_support=False), 3456, 3),
    ('T-21', dict(tech='DMLS', material='Нержавеющая сталь 316L', quality='Стандартное', color='металлик',
                  bbox=(40, 40, 30), volume=10, qty=2, needs_support=False), 19320, 1),
    ('T-22', dict(tech='DMLS', material='Нержавеющая сталь 316L', quality='Стандартное', color='металлик',
                  bbox=(90, 50, 40), volume=20, qty=1, pp=['Шлифовка'], delivery='COURIER',
                  needs_support=False), 20070, 4),
    ('T-23', dict(tech='DMLS', material='Нержавеющая сталь 316L', quality='Стандартное', color='металлик',
                  bbox=(60, 60, 60), volume=22, qty=1, needs_support=True), 22747, 1),
    ('T-24', dict(tech='DMLS', material='Нержавеющая сталь 316L', quality='Стандартное', color='металлик',
                  bbox=(150, 30, 30), volume=30, qty=2, pp=['Шлифовка'], needs_support=False), 52760, 2),
]


@pytest.mark.parametrize('name,kw,expected_total,expected_days', CASES, ids=[c[0] for c in CASES])
def test_reference_pricing_parity_t01_t24(catalog_data, client_user, name, kw, expected_total, expected_days):
    kwargs = dict(kw)
    needs_support = kwargs.pop('needs_support')
    order, mv = _make_order_for_pricing(client_user, **kwargs)
    q = pricing_services.calculate(order, mv, needs_support=needs_support, queue_wait_h=0.0)
    assert abs(int(q.total) - expected_total) <= 1, name
    assert q.estimated_days == expected_days, name
    assert q.tariff_version is not None


def test_adjustment_and_negative_total_guard(catalog_data, client_user):
    order, mv = _make_order_for_pricing(
        client_user, tech='FDM', material='PLA', quality='Стандартное', color='белый', volume=18,
    )
    q1 = pricing_services.calculate(order, mv)
    assert int(q1.total) == 300

    q2 = pricing_services.apply_adjustment(order, Decimal('-100.00'))
    assert int(q2.total) == 200
    assert Quote.objects.filter(order=order, is_current=True).count() == 1
    q1.refresh_from_db()
    assert q1.is_current is False

    with pytest.raises(DomainError) as exc:
        pricing_services.apply_adjustment(order, '-500')
    assert exc.value.code == 'validation'

    with pytest.raises(DomainError) as exc_nan:
        pricing_services.apply_adjustment(order, 'NaN')
    assert exc_nan.value.code == 'validation'


def test_queue_wait_increases_estimated_days():
    r0 = compute_quote(
        volume_cm3=18, quantity=1, needs_support=False, density=1.24, price_per_gram=Decimal('2.5'),
        fill_factor=0.35, support_factor=0.15, flow_cm3_h=12, hourly_rate=220, setup_cost=100,
        price_factor=1.0, queue_wait_h=0.0,
    )
    r1 = compute_quote(
        volume_cm3=18, quantity=1, needs_support=False, density=1.24, price_per_gram=Decimal('2.5'),
        fill_factor=0.35, support_factor=0.15, flow_cm3_h=12, hourly_rate=220, setup_cost=100,
        price_factor=1.0, queue_wait_h=25.0,
    )
    assert r0.days_print == 1
    assert r1.days_print == 2
