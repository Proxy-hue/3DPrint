"""PaymentProvider: заглушка (PAY_STUB_ENABLED). Реальный шлюз — вне объёма (OOS-03)."""
from django.conf import settings

from .models import Payment


class PaymentProvider:
    name = 'STUB'

    def charge(self, order, amount):
        raise NotImplementedError


class StubPaymentProvider(PaymentProvider):
    def charge(self, order, amount):
        return Payment.objects.create(order=order, amount=amount, provider=self.name, status='SUCCEEDED')


def get_provider():
    return StubPaymentProvider()


def pay(order, amount):
    return get_provider().charge(order, amount)


def stub_enabled():
    return getattr(settings, 'PAY_STUB_ENABLED', True)
