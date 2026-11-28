"""Тесты заглушки оплаты payment."""
import pytest

from orders import services as os_
from payment import services as ps
from payment.models import Payment
from users.models import User

pytestmark = pytest.mark.django_db


def test_stub_payment_creates_succeeded_record():
    u = User.objects.create_user(email='pay@test.local', password='pass12345', role='CLIENT')
    order = os_.create_draft(u)
    p = ps.pay(order, 1250)
    assert isinstance(p, Payment)
    assert p.provider == 'STUB'
    assert p.status == 'SUCCEEDED'
    assert int(p.amount) == 1250
    assert ps.stub_enabled() is True
