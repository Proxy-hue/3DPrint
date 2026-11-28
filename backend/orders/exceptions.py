"""Бизнес-исключения и единый обработчик ошибок DRF ({code, detail})."""
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class DomainError(Exception):
    def __init__(self, message, code='error', status=400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status = status


def api_exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response({'code': exc.code, 'detail': exc.message}, status=exc.status)
    if isinstance(exc, DjangoValidationError):
        msg = ' '.join(exc.messages) if hasattr(exc, 'messages') else str(exc)
        return Response({'code': 'validation', 'detail': msg}, status=400)
    return drf_exception_handler(exc, context)
