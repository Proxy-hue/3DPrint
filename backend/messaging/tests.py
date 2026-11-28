"""Тесты модуля messaging: переписка по заказу и прикрепление исправленной 3D-модели."""
import io
import struct

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from catalog.models import Color, DeliveryMethod, Material, PickupPoint, QualityProfile, Technology
from messaging import services as messaging_services
from messaging.models import Message
from notifications.models import Notification
from orders import services as os_
from orders.models import Status
from users.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _isolated_media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


def _cube_stl() -> bytes:
    pts = [
        (0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0),
        (0, 0, 20), (20, 0, 20), (20, 20, 20), (0, 20, 20),
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
def msg_env():
    call_command('loaddata', 'initial_catalog', verbosity=0)
    client = User.objects.create_user(email='msg_client@test.local', password='pass12345', role='CLIENT')
    other = User.objects.create_user(email='msg_other@test.local', password='pass12345', role='CLIENT')
    manager = User.objects.create_user(email='msg_mgr@test.local', password='pass12345', role='MANAGER')

    t = Technology.objects.get(code='FDM')
    m = Material.objects.get(name='PLA')
    q = QualityProfile.objects.get(technology=t, name='Стандартное')
    c = Color.objects.get(name='белый')
    dm = DeliveryMethod.objects.get(type='PICKUP')
    pt = PickupPoint.objects.filter(delivery_method=dm).first()

    o = os_.create_draft(client, {
        'technology': str(t.pk), 'material': str(m.pk), 'quality_profile': str(q.pk),
        'color': str(c.pk), 'delivery_method': str(dm.pk), 'pickup_point': str(pt.pk),
    })
    os_.attach_model(o, client, 'v1.stl', _cube_stl())
    os_.confirm(o, client)
    o.refresh_from_db()
    return {'client': client, 'other': other, 'manager': manager, 'order': o}


def test_messaging_service_and_clarification_reupload(msg_env):
    order = msg_env['order']
    client = msg_env['client']
    manager = msg_env['manager']

    os_.decision(order, manager, 'clarify', 'Уточните толщину стенки.')
    assert order.status == Status.CLARIFICATION
    assert Message.objects.filter(order=order).count() == 1

    c_api = APIClient()
    c_api.force_authenticate(client)
    other_api = APIClient()
    other_api.force_authenticate(msg_env['other'])

    assert other_api.get(f'/api/orders/{order.pk}/messages').status_code == 404

    stl = io.BytesIO(_cube_stl())
    stl.name = 'v2.stl'
    r = c_api.post(
        f'/api/orders/{order.pk}/messages',
        {'text': 'Исправленная модель', 'file': stl},
        format='multipart',
    )
    assert r.status_code == 201
    assert r.data['model_version'] == 2

    order.refresh_from_db()
    assert order.status == Status.CHECKED
    assert Notification.objects.filter(user=manager, order=order).exists()
    assert messaging_services.list_for(order).count() == 2
