"""Тесты оркестрации заказов, FSM (14 статусов), RBAC и REST API модуля orders."""
import io
import struct
import zipfile
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import (
    AuditLog, Color, DeliveryMethod, Material, PickupPoint, PostProcessing,
    Printer, QualityProfile, Technology,
)
from orders import adapters
from orders import services as os_
from orders.exceptions import DomainError
from orders.models import InsertOnlyError, Order, OrderEvent, Status
from pricing import services as pricing_services
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _binary_stl_cube(dx=20.0, dy=20.0, dz=20.0) -> bytes:
    """Минимальный замкнутый куб в бинарном STL для реального разбора trimesh."""
    pts = [
        (0, 0, 0), (dx, 0, 0), (dx, dy, 0), (0, dy, 0),
        (0, 0, dz), (dx, 0, dz), (dx, dy, dz), (0, dy, dz),
    ]
    tris = [
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    ]
    buf = bytearray(b'cube'.ljust(80, b'\0') + struct.pack('<I', len(tris)))
    for a, b, c in tris:
        buf += struct.pack('<3f', 0.0, 0.0, 0.0)
        for idx in (a, b, c):
            buf += struct.pack('<3f', *[float(v) for v in pts[idx]])
        buf += struct.pack('<H', 0)
    return bytes(buf)


@pytest.fixture
def env_data():
    call_command('loaddata', 'initial_catalog', verbosity=0)
    return {
        'client': User.objects.create_user(email='client@test.local', password='pass12345', role='CLIENT'),
        'other': User.objects.create_user(email='other@test.local', password='pass12345', role='CLIENT'),
        'manager': User.objects.create_user(email='manager@test.local', password='pass12345', role='MANAGER'),
        'admin': User.objects.create_superuser(email='admin@test.local', password='pass12345', role='ADMIN'),
    }


def _api(user=None):
    c = APIClient()
    if user is not None:
        c.force_authenticate(user)
    return c


def _draft_with_params(client_user, *, tech='FDM', material='PLA', quality='Стандартное',
                       color='белый', pp=(), delivery='PICKUP', qty=1):
    t = Technology.objects.get(code=tech)
    m = Material.objects.get(name=material)
    q = QualityProfile.objects.get(technology=t, name=quality)
    c = Color.objects.get(name=color)
    dm = DeliveryMethod.objects.get(type=delivery)
    pickup = PickupPoint.objects.filter(delivery_method=dm).first() if delivery == 'PICKUP' else None
    o = os_.create_draft(client_user, {
        'technology': str(t.pk),
        'material': str(m.pk),
        'quality_profile': str(q.pk),
        'color': str(c.pk),
        'delivery_method': str(dm.pk),
        'pickup_point': str(pickup.pk) if pickup else None,
        'quantity': qty,
        'post_processing': [str(PostProcessing.objects.get(name=n).pk) for n in pp],
    })
    return o


def test_full_order_lifecycle_with_scheduling_hook(env_data, monkeypatch):
    o = _draft_with_params(env_data['client'])
    os_.attach_model(o, env_data['client'], 'cube.stl', _binary_stl_cube(20, 20, 20))
    os_.confirm(o, env_data['client'])
    o.refresh_from_db()
    assert o.status == Status.CHECKED
    assert pricing_services.current_quote(o) is not None

    os_.decision(o, env_data['manager'], 'approve')
    assert o.status == Status.AWAITING_PAYMENT

    os_.pay(o, env_data['client'])
    assert o.status == Status.PAID

    # Проверяем, что PAID -> DISTRIBUTED заблокирован без назначения принтера
    with pytest.raises(DomainError) as exc:
        os_.change_status(o, env_data['manager'], Status.DISTRIBUTED)
    assert exc.value.code == 'no_assignment'

    # После подключения модуля scheduling с назначением переход разрешается
    monkeypatch.setattr(adapters, 'current_assignment', lambda order: object())
    os_.change_status(o, env_data['manager'], Status.DISTRIBUTED)
    for st in (Status.PRINTING, Status.READY, Status.COMPLETED):
        os_.change_status(o, env_data['manager'], st)
    assert o.status == Status.COMPLETED
    assert OrderEvent.objects.filter(order=o, type='STATUS_CHANGED').count() >= 7


def test_transition_guards_and_reasons(env_data):
    o = _draft_with_params(env_data['client'], pp=['Шлифовка'])
    os_.attach_model(o, env_data['client'], 'cube.stl', _binary_stl_cube(20, 20, 20))
    os_.confirm(o, env_data['client'])
    o.refresh_from_db()

    with pytest.raises(DomainError) as e_reason:
        os_.decision(o, env_data['manager'], 'reject', '')
    assert e_reason.value.code == 'reason_required'

    # Недопустимый прямой переход CHECKED -> COMPLETED
    with pytest.raises(DomainError) as e_inv:
        os_.change_status(o, env_data['manager'], Status.COMPLETED)
    assert e_inv.value.code == 'invalid_transition'


def test_optimistic_locking_and_past_desired_date(env_data):
    o = _draft_with_params(env_data['client'])
    stale = Order.objects.get(pk=o.pk)
    os_.update_draft(o, env_data['client'], {'quantity': 3}, recalc=False)
    with pytest.raises(DomainError) as exc:
        os_.update_draft(stale, env_data['client'], {'quantity': 4, 'version': stale.version}, recalc=False)
    assert exc.value.status == 409

    past = (timezone.localdate() - timedelta(days=1)).isoformat()
    with pytest.raises(DomainError) as exc_d:
        os_.update_draft(o, env_data['client'], {'desired_date': past}, recalc=False)
    assert exc_d.value.code == 'validation'


def test_insert_only_order_event(env_data):
    o = _draft_with_params(env_data['client'])
    ev = o.events.first()
    with pytest.raises(InsertOnlyError):
        ev.save()
    with pytest.raises(InsertOnlyError):
        ev.delete()


def test_rest_api_list_pagination_quote_get_and_rbac(env_data):
    c_client = _api(env_data['client'])
    c_other = _api(env_data['other'])
    c_mgr = _api(env_data['manager'])
    c_admin = _api(env_data['admin'])

    # Загрузка модели через POST /api/orders (multipart) сразу создаёт черновик
    stl = io.BytesIO(_binary_stl_cube(30, 30, 10))
    stl.name = 'part.stl'
    r = c_client.post('/api/orders', {'file': stl}, format='multipart')
    assert r.status_code == 201
    oid = r.data['id']
    assert r.data['model']['format'] == 'STL'

    # GET /api/orders возвращает count и results (совместимость с фронтендом)
    r_list = c_client.get('/api/orders')
    assert r_list.status_code == 200
    assert r_list.data['count'] == 1
    assert len(r_list.data['results']) == 1

    # Чужой клиент не видит заказ, менеджер не видит чужой DRAFT
    assert c_other.get(f'/api/orders/{oid}').status_code == 404
    assert c_mgr.get(f'/api/orders/{oid}').status_code == 404

    # PATCH параметров черновика пересчитывает проверку и смету
    t = Technology.objects.get(code='FDM')
    m = Material.objects.get(name='PLA')
    q = QualityProfile.objects.get(technology=t, name='Стандартное')
    col = Color.objects.get(name='белый')
    dm = DeliveryMethod.objects.get(type='PICKUP')
    pt = PickupPoint.objects.filter(delivery_method=dm).first()
    r_patch = c_client.patch(f'/api/orders/{oid}', {
        'technology': str(t.pk),
        'material': str(m.pk),
        'quality_profile': str(q.pk),
        'color': str(col.pk),
        'delivery_method': str(dm.pk),
        'pickup_point': str(pt.pk),
    }, format='json')
    assert r_patch.status_code == 200
    assert r_patch.data['quote']['total'] == 300

    # GET /api/orders/{id}/quote по спецификации 5.3.4 (F-CLI-06)
    r_quote = c_client.get(f'/api/orders/{oid}/quote')
    assert r_quote.status_code == 200
    assert r_quote.data['quote']['total'] == 300
    assert r_quote.data['validation']['verdict'] == 'OK'
    assert r_quote.data['validation']['issues'] == []
    assert r_quote.data['validation']['needs_support'] is False
    assert r_quote.data['ready'] is True

    # Скачивание модели и проверка ссылки /file
    r_file = c_client.get(f'/api/orders/{oid}/model/1/file')
    assert r_file.status_code == 200
    assert r_file.data['download_url'].endswith('/model/1/download')
    assert c_client.get(r_file.data['download_url']).status_code == 200

    # Подтверждение заказа
    assert c_client.post(f'/api/orders/{oid}/confirm', {}, format='json').status_code == 200
    assert c_mgr.get('/api/orders').data['count'] == 1

    # Корректировка цены доступна только ADMIN и пишется в catalog.models.AuditLog
    r_forbidden = c_mgr.post(
        f'/api/orders/{oid}/adjustment', {'adjustment': -50, 'reason': 'x'}, format='json',
    )
    assert r_forbidden.status_code == 403
    r_adj = c_admin.post(
        f'/api/orders/{oid}/adjustment', {'adjustment': -50, 'reason': 'Скидка'}, format='json',
    )
    assert r_adj.status_code == 200
    assert r_adj.data['quote']['total'] == 250
    assert AuditLog.objects.filter(entity_type='pricing.Quote', action='UPDATE').exists()

    # Повтор заказа
    r_rep = c_client.post(f'/api/orders/{oid}/repeat', {}, format='json')
    assert r_rep.status_code == 201
    assert r_rep.data['status'] == 'DRAFT'
    assert r_rep.data['model']['version'] == 1


def test_validation_e04_e05_e06_via_catalog(env_data):
    # E-05: Красный цвет несовместим с покрытием SLA / Стандартная смола (проверяем через Покраска/металл)
    o = _draft_with_params(
        env_data['client'], tech='DMLS', material='Нержавеющая сталь 316L',
        quality='Стандартное', color='металлик', pp=['Покраска'],
    )
    os_.attach_model(o, env_data['client'], 'metal.stl', _binary_stl_cube(20, 20, 20))
    os_.confirm(o, env_data['client'])
    o.refresh_from_db()
    assert o.status == Status.MANUAL_REVIEW
    codes = {i['code'] for i in o.model_meta['validation']['issues']}
    assert 'E-05' in codes

    # E-06 без E-04 при списании единственного DMLS принтера (P-05)
    Printer.objects.filter(name='DMLS-01').update(status='RETIRED')
    o2 = _draft_with_params(
        env_data['client'], tech='DMLS', material='Нержавеющая сталь 316L',
        quality='Стандартное', color='металлик',
    )
    os_.attach_model(o2, env_data['client'], 'metal2.stl', _binary_stl_cube(20, 20, 20))
    os_.confirm(o2, env_data['client'])
    o2.refresh_from_db()
    assert o2.status == Status.MANUAL_REVIEW
    codes2 = {i['code'] for i in o2.model_meta['validation']['issues']}
    assert 'E-06' in codes2
    assert 'E-04' not in codes2


def test_upload_rejects_bad_formats_and_zip_bomb(env_data):
    c_client = _api(env_data['client'])

    step = io.BytesIO(b'ISO-10303-21;')
    step.name = 'part.step'
    r1 = c_client.post('/api/orders', {'file': step}, format='multipart')
    assert r1.status_code == 400
    assert r1.data['code'] == 'E-01'

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('3D/3dmodel.model', b'0' * (20 * 1024 * 1024))
    bomb = io.BytesIO(buf.getvalue())
    bomb.name = 'bomb.3mf'
    r2 = c_client.post('/api/orders', {'file': bomb}, format='multipart')
    assert r2.status_code == 400
    assert r2.data['code'] == 'E-02'


def test_temp_auth_smoke(env_data):
    anon = APIClient()
    assert anon.get('/api/auth/csrf').status_code == 200
    r_reg = anon.post('/api/auth/register', {
        'email': 'new@test.local',
        'password': 'StrongPassword123!',
        'full_name': 'Иван Тестов',
        'consent': True,
    }, format='json')
    assert r_reg.status_code == 201
    assert anon.get('/api/auth/me').data['email'] == 'new@test.local'
    assert anon.post('/api/auth/logout', {}, format='json').status_code == 200
