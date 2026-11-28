"""Тесты scheduling на БД (pytest-django, PostgreSQL в CI)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from catalog.models import Color, Material, Printer, QualityProfile, Technology
from orders.models import Order
from users.models import User

from . import services
from .models import Assignment
from .services import AssignmentError

pytestmark = [pytest.mark.django_db, pytest.mark.urls('common.testing_urls')]

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
SMALL = [30, 30, 30]


@pytest.fixture(autouse=True)
def catalog_data():
    call_command('loaddata', 'initial_catalog', verbosity=0)


@pytest.fixture
def client_user():
    return User.objects.create_user(
        email='client@test.com', password='pass12345', role='CLIENT'
    )


def make_order(client_user, tech='FDM', material='PLA', color='белый'):
    technology = Technology.objects.get(code=tech)
    return Order.objects.create(
        number=f'T-{uuid.uuid4().hex[:8]}', client=client_user,
        status='PAID', technology=technology,
        material=Material.objects.get(name=material),
        color=Color.objects.get(name=color),
        quality_profile=QualityProfile.objects.filter(
            technology=technology
        ).first(),
    )


def params(order, bbox=SMALL, hours=5.0):
    return dict(
        technology=order.technology, material=order.material,
        color=order.color, bbox=bbox, print_hours=hours,
    )


def printer(name):
    return Printer.objects.select_related('workshop').get(name=name)


def test_recommend_returns_orders_contract(client_user):
    order = make_order(client_user)
    result = services.recommend(**params(order), exclude_order=order, now=NOW)
    assert [r['printer'] for r in result['top']] == [
        'FDM-01', 'FDM-02', 'FDM-XL'
    ]
    assert result['others'] == []
    assert result['error_code'] is None
    first = result['top'][0]
    assert {'printer_id', 'printer', 'workshop', 'score', 'queue_hours',
            'planned_start', 'planned_end'} <= set(first)
    assert first['planned_start'] == NOW
    assert result['top'][2]['reserve'] is True


def test_recommend_large_model_needs_large_format(client_user):
    order = make_order(client_user)
    result = services.recommend(**params(order, bbox=[400, 300, 60]), now=NOW)
    assert [r['printer'] for r in result['top']] == ['FDM-XL']
    assert result['required_specialization'] == 'LARGE_FORMAT'
    excluded = {e['printer']: e['reasons'] for e in result['excluded']}
    assert 'SIZE' in excluded['FDM-01']


def test_recommend_without_printer_gives_e06(client_user):
    Printer.objects.filter(name='DMLS-01').update(status='RETIRED')
    order = make_order(
        client_user, tech='DMLS', material='Нержавеющая сталь 316L',
        color='металлик',
    )
    result = services.recommend(**params(order), now=NOW)
    assert result['top'] == [] and result['error_code'] == 'E-06'


def test_assign_and_current_assignment(client_user):
    order = make_order(client_user)
    assignment = services.assign(
        order=order, printer=services.get_printer(printer('FDM-01').pk),
        print_hours=5, actor_reason='', is_manual=False, now=NOW,
    )
    current = services.current_assignment(order)
    assert current.pk == assignment.pk
    assert current.printer.workshop.name == 'Основной цех'
    assert current.planned_start == NOW
    assert current.planned_end == NOW + timedelta(hours=6)
    assert current.material_id == order.material_id
    assert order.assignments.filter(is_current=True).count() == 1


def test_reassign_replaces_and_clear_removes(client_user):
    order = make_order(client_user)
    services.assign(order=order, printer=printer('FDM-01'), print_hours=5,
                    now=NOW)
    services.assign(order=order, printer=printer('FDM-02'), print_hours=5,
                    actor_reason='  вручную  ', is_manual=True, now=NOW)
    current = services.current_assignment(order)
    assert current.printer.name == 'FDM-02'
    assert current.is_manual and current.reason == 'вручную'
    assert Assignment.objects.filter(order=order).count() == 2

    services.clear_assignment(order)
    assert services.current_assignment(order) is None


def test_queue_wait_hours_follow_least_loaded_printer(client_user):
    probe = make_order(client_user)
    assert services.queue_wait_hours(
        technology=probe.technology, material=probe.material,
        color=probe.color, bbox=SMALL, now=NOW,
    ) == 0.0
    for name, hours in (('FDM-01', 10), ('FDM-02', 20), ('FDM-XL', 30)):
        services.assign(
            order=make_order(client_user), printer=printer(name),
            print_hours=hours, now=NOW,
        )
    assert services.queue_wait_hours(
        technology=probe.technology, material=probe.material,
        color=probe.color, bbox=SMALL, now=NOW,
    ) == 10.0


def test_recommendation_ignores_own_assignment(client_user):
    order = make_order(client_user)
    services.assign(order=order, printer=printer('FDM-01'), print_hours=14,
                    now=NOW)
    result = services.recommend(
        **params(order, hours=14), exclude_order=order, now=NOW
    )
    assert result['top'][0]['printer'] == 'FDM-01'
    assert result['top'][0]['queue_hours'] == 0.0


def test_orders_workshop_filter_uses_assignments_relation(client_user):
    order = make_order(client_user)
    services.assign(order=order, printer=printer('FDM-02'), print_hours=5,
                    now=NOW)
    workshop = printer('FDM-02').workshop
    found = Order.objects.filter(
        assignments__is_current=True,
        assignments__printer__workshop_id=workshop.pk,
    )
    assert list(found) == [order]


def test_auto_assign_metal_goes_to_dmls(client_user):
    order = make_order(
        client_user, tech='DMLS', material='Нержавеющая сталь 316L',
        color='металлик',
    )
    assignment = services.auto_assign(order=order, **params(order), now=NOW)
    assert assignment.printer.name == 'DMLS-01'
    assert assignment.is_manual is False


def test_auto_assign_without_printer_fails(client_user):
    Printer.objects.filter(name='DMLS-01').update(status='RETIRED')
    order = make_order(
        client_user, tech='DMLS', material='Нержавеющая сталь 316L',
        color='металлик',
    )
    with pytest.raises(AssignmentError) as error:
        services.auto_assign(order=order, **params(order), now=NOW)
    assert error.value.code == 'E-06'


def test_load_reflects_assignment(client_user):
    services.assign(order=make_order(client_user), printer=printer('FDM-01'),
                    print_hours=14, now=NOW)
    load = services.get_load(now=NOW)
    by_name = {p.printer_name: p for p in load['printers']}
    assert load['capacity_hours'] == 140.0
    assert by_name['FDM-01'].planned_hours == 14.0
    assert by_name['FDM-01'].load_percent == 10.0
    assert by_name['FDM-02'].load_percent == 0.0


def test_load_endpoint_permissions(client_user):
    manager = User.objects.create_user(
        email='m@test.com', password='x', role='MANAGER'
    )
    denied = APIClient()
    denied.force_authenticate(client_user)
    assert denied.get('/api/load/').status_code == 403

    allowed = APIClient()
    allowed.force_authenticate(manager)
    response = allowed.get('/api/load/')
    assert response.status_code == 200
    data = response.json()
    assert data['horizon_days'] == 7
    assert 'FDM-01' in {p['printer_name'] for p in data['printers']}
