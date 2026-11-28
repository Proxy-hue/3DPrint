"""Постановка фоновых задач в django-rq после коммита транзакции.

При TASKS_SYNC=True или недоступном Redis задачи выполняются синхронно.
"""
import importlib
import logging

from django.conf import settings
from django.db import transaction

logger = logging.getLogger(__name__)


def _resolve(path):
    mod, _, name = path.rpartition('.')
    return getattr(importlib.import_module(mod), name)


def _dispatch(func_path, *args):
    try:
        import django_rq
        return django_rq.get_queue('default').enqueue(func_path, *args)
    except Exception as exc:
        logger.warning('RQ недоступен (%s), выполняем %s синхронно.', exc, func_path)
        return _resolve(func_path)(*args)


def enqueue(func_path, *args):
    if getattr(settings, 'TASKS_SYNC', False):
        return _resolve(func_path)(*args)
    transaction.on_commit(lambda: _dispatch(func_path, *args))
