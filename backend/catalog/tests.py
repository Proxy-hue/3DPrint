"""Тесты catalog на БД (pytest-django, PostgreSQL в CI)."""
import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse
from rest_framework.test import APIClient

from users.models import User

from . import services
from .audit import record
from .models import (
    AuditLog, Color, DeliveryMethod, Material, PickupPoint, PostProcessing,
    Printer, QualityProfile, TariffVersion, Technology, Workshop,
)

pytestmark = [pytest.mark.django_db, pytest.mark.urls('common.testing_urls')]


@pytest.fixture
def catalog_data():
    call_command('loaddata', 'initial_catalog', verbosity=0)


@pytest.fixture
def admin_user():
    return User.objects.create_superuser(
        email='admin@test.com', password='pass12345', role='ADMIN'
    )


@pytest.fixture
def manager_user():
    return User.objects.create_user(
        email='manager@test.com', password='pass12345', role='MANAGER',
        is_staff=True,
    )


@pytest.fixture
def client_user():
    return User.objects.create_user(
        email='client@test.com', password='pass12345', role='CLIENT'
    )


def api_as(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def rows(response):
    data = response.json()
    return data['results'] if isinstance(data, dict) else data


# --- Данные и ограничения ---

def test_fixture_loads_reference_data(catalog_data):
    assert Technology.objects.count() == 3
    assert QualityProfile.objects.count() == 6
    assert Material.objects.count() == 6
    assert Color.objects.count() == 7
    assert PostProcessing.objects.count() == 3
    assert DeliveryMethod.objects.count() == 2
    assert PickupPoint.objects.count() == 2
    assert Workshop.objects.count() == 2
    assert Printer.objects.count() == 6
    assert services.get_tariff_params()['min_cost'] == 300


def test_only_one_main_workshop(catalog_data):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Workshop.objects.create(name='Ещё один основной', is_main=True)


def test_printer_dimensions_must_be_positive(catalog_data):
    printer = Printer.objects.get(name='FDM-01')
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Printer.objects.create(
                name='Bad', workshop=printer.workshop,
                technology=printer.technology, max_x=0, max_y=10, max_z=10,
            )


def test_specialized_printer_must_be_in_main_workshop(catalog_data):
    second = Workshop.objects.get(is_main=False)
    printer = Printer.objects.get(name='DMLS-01')
    printer.workshop = second
    with pytest.raises(ValidationError):
        printer.clean()


def test_used_reference_records_cannot_be_deleted(catalog_data):
    with pytest.raises(ProtectedError):
        Technology.objects.get(code='FDM').delete()
    with pytest.raises(ProtectedError):
        Workshop.objects.get(is_main=True).delete()


def test_quality_profile_unique_per_technology(catalog_data):
    existing = QualityProfile.objects.first()
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            QualityProfile.objects.create(
                technology=existing.technology, name=existing.name,
                layer_height_mm=0.2, flow_cm3_h=10,
            )


def test_only_one_active_tariff_version(catalog_data):
    TariffVersion.objects.create(is_active=True, params={'min_cost': 500})
    assert TariffVersion.objects.filter(is_active=True).count() == 1
    params = services.get_tariff_params()
    assert params['min_cost'] == 500
    assert params['printer_hours_per_day'] == 20      # значение по умолчанию


# --- Совместимость (через ORM) ---

def _combo(material, color, quality, tech, posts=(), delivery=None,
           point=None):
    return services.check_compatibility(
        technology=Technology.objects.get(code=tech),
        material=Material.objects.get(name=material),
        quality_profile=QualityProfile.objects.get(
            technology__code=tech, name=quality
        ),
        color=Color.objects.get(name=color),
        post_processings=[
            PostProcessing.objects.get(code=code) for code in posts
        ],
        delivery_method=(
            DeliveryMethod.objects.get(type=delivery) if delivery else None
        ),
        pickup_point=PickupPoint.objects.first() if point else None,
    )


def test_compatibility_valid_order(catalog_data):
    assert _combo('PLA', 'белый', 'Стандартное', 'FDM',
                  posts=['SANDING', 'PAINTING'], delivery='COURIER') == []


def test_compatibility_painting_not_for_metal(catalog_data):
    issues = _combo('Нержавеющая сталь 316L', 'металлик', 'Стандартное',
                    'DMLS', posts=['PAINTING'])
    assert [i.reason for i in issues] == ['POST_TECHNOLOGY']


def test_compatibility_painting_not_for_transparent(catalog_data):
    issues = _combo('Стандартная смола', 'прозрачный', 'Стандартное', 'SLA',
                    posts=['PAINTING'])
    assert [i.reason for i in issues] == ['POST_TRANSPARENT']


def test_compatibility_pickup_needs_point(catalog_data):
    assert [i.reason for i in _combo(
        'PLA', 'белый', 'Стандартное', 'FDM', delivery='PICKUP'
    )] == ['PICKUP_POINT_REQUIRED']
    assert _combo('PLA', 'белый', 'Стандартное', 'FDM',
                  delivery='PICKUP', point=True) == []


# --- API ---

def test_catalog_requires_authentication(catalog_data):
    response = api_as().get('/api/catalog/materials/')
    assert response.status_code in (401, 403)


def test_client_does_not_see_cost_fields(catalog_data, client_user):
    response = api_as(client_user).get('/api/catalog/materials/')
    assert response.status_code == 200
    item = rows(response)[0]
    assert 'price_per_gram' not in item and 'density' not in item
    technology = rows(api_as(client_user).get('/api/catalog/technologies/'))
    assert 'hourly_rate' not in technology[0]


def test_manager_sees_cost_fields(catalog_data, manager_user):
    response = api_as(manager_user).get('/api/catalog/materials/')
    assert 'price_per_gram' in rows(response)[0]


def test_inactive_records_are_hidden(catalog_data, client_user):
    Material.objects.filter(name='ABS').update(is_active=False)
    names = [m['name'] for m in rows(
        api_as(client_user).get('/api/catalog/materials/')
    )]
    assert 'ABS' not in names and len(names) == 5


def test_equipment_only_for_manager_and_admin(catalog_data, client_user,
                                              manager_user):
    assert api_as(client_user).get('/api/printers/').status_code == 403
    assert api_as(client_user).get('/api/workshops/').status_code == 403
    response = api_as(manager_user).get('/api/printers/')
    assert response.status_code == 200
    assert len(rows(response)) == 6


def test_catalog_is_read_only_via_api(catalog_data, admin_user):
    response = api_as(admin_user).post(
        '/api/catalog/materials/', {'name': 'X'}, format='json'
    )
    assert response.status_code == 405
    assert api_as(admin_user).delete(
        f'/api/printers/{Printer.objects.first().pk}/'
    ).status_code == 405


def test_compatibility_matrix_endpoint(catalog_data, client_user):
    response = api_as(client_user).get('/api/catalog/compatibility/')
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {'materials', 'quality_profiles',
                         'post_processing', 'delivery_methods'}
    painting = [p for p in data['post_processing']
                if p['code'] == 'PAINTING'][0]
    assert str(Technology.objects.get(code='DMLS').pk) in (
        painting['incompatible_technologies']
    )
    assert painting['forbids_transparent'] is True


# --- Аудит и Django admin ---

def test_admin_changes_are_audited(catalog_data, admin_user):
    client = api_as()
    client.force_login(admin_user)

    response = client.post(reverse('admin:catalog_workshop_add'), {
        'name': 'Цех № 3', 'address': 'ул. Новая, 3', 'is_active': 'on',
        '_save': '',
    })
    assert response.status_code == 302
    workshop = Workshop.objects.get(name='Цех № 3')
    created = AuditLog.objects.get(entity_id=workshop.pk, action='CREATE')
    assert created.actor_id == admin_user.pk
    assert created.before is None and created.after['name'] == 'Цех № 3'

    response = client.post(
        reverse('admin:catalog_workshop_change', args=[workshop.pk]),
        {'name': 'Цех № 3А', 'address': 'ул. Новая, 3', 'is_active': 'on',
         '_save': ''},
    )
    assert response.status_code == 302
    updated = AuditLog.objects.get(entity_id=workshop.pk, action='UPDATE')
    assert updated.before['name'] == 'Цех № 3'
    assert updated.after['name'] == 'Цех № 3А'


def test_catalog_admin_is_closed_for_manager(catalog_data, manager_user):
    client = api_as()
    client.force_login(manager_user)
    response = client.get(reverse('admin:catalog_workshop_changelist'))
    assert response.status_code == 403


def test_audit_log_is_insert_only(catalog_data, admin_user):
    workshop = Workshop.objects.first()
    entry = record(admin_user, workshop, 'UPDATE', {'a': 1}, {'a': 2})
    entry.after = {'a': 3}
    with pytest.raises(ValidationError):
        entry.save()
    with pytest.raises(ValidationError):
        entry.delete()
