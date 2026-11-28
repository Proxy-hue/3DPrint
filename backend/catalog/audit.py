"""Аудит изменений справочников через Django admin (F-MGR-10)."""
import json

from django.core.serializers.json import DjangoJSONEncoder

from .models import AuditLog

_SKIP = {'created_at', 'updated_at', 'password', 'last_login'}


def snapshot(obj):
    """Словарь значений полей объекта (включая M2M) для журнала."""
    data = {}
    for field in obj._meta.concrete_fields:
        if field.name in _SKIP:
            continue
        data[field.name] = field.value_from_object(obj)
    for field in obj._meta.many_to_many:
        if obj.pk is None:
            data[field.name] = []
        else:
            related = getattr(obj, field.name).all()
            data[field.name] = sorted(str(item.pk) for item in related)
    return json.loads(json.dumps(data, cls=DjangoJSONEncoder))


def record(actor, obj, action, before, after, entity_id=None):
    return AuditLog.objects.create(
        actor=actor if getattr(actor, 'is_authenticated', False) else None,
        entity_type=obj._meta.label,
        entity_id=entity_id or obj.pk,
        action=action,
        before=before,
        after=after,
    )
