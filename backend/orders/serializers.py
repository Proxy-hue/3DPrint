"""Сериализация объектов заказа в JSON для REST API (чистые функции без ModelSerializer)."""
from . import adapters
from .models import Status
from .permissions import CLIENT, MANAGER, get_role
from .services import FINAL, TRANSITIONS, can_pass_guard, quote_state


def _s(x):
    return str(x) if x is not None else None


def _display_name(u):
    if not u:
        return 'Система'
    full = getattr(u, 'full_name', '') or u.get_full_name()
    return full or u.email


def user_brief(u):
    return {
        'id': _s(u.id),
        'full_name': _display_name(u),
        'email': u.email,
        'role': get_role(u) or getattr(u, 'role', CLIENT),
    }


def _ref(obj, extra=()):
    if not obj:
        return None
    d = {'id': _s(obj.pk), 'name': obj.name}
    for k in extra:
        d[k] = getattr(obj, k)
    return d


def model_dto(mv):
    if not mv:
        return None
    return {
        'version': mv.version,
        'file_name': mv.file_name,
        'format': mv.format,
        'size_bytes': mv.size_bytes,
        'bbox': [mv.bbox_x, mv.bbox_y, mv.bbox_z],
        'volume_cm3': mv.volume_cm3,
        'body_count': mv.body_count,
        'analysis': getattr(mv, 'analysis', {}),
    }


def quote_dto(q):
    if not q:
        return None
    return {
        'id': _s(q.id),
        'total': int(q.total),
        'cost_material': float(q.cost_material),
        'cost_machine': float(q.cost_machine),
        'cost_post': float(q.cost_post),
        'cost_delivery': float(q.cost_delivery),
        'adjustment': float(q.adjustment),
        'print_hours': float(q.print_hours),
        'mass_g': float(q.mass_g),
        'estimated_days': q.estimated_days,
    }


def validation_dto(vr):
    if not vr:
        return None
    return {'verdict': vr.verdict, 'issues': vr.issues, 'needs_support': vr.needs_support}


def summary(o):
    from pricing import services as pricing_services
    q = pricing_services.current_quote(o)
    return {
        'id': _s(o.id),
        'number': o.number,
        'status': o.status,
        'status_label': Status(o.status).label,
        'priority': o.priority,
        'quantity': o.quantity,
        'material': _ref(o.material),
        'technology': {'id': _s(o.technology_id), 'code': o.technology.code} if o.technology else None,
        'total': int(q.total) if q else None,
        'created_at': o.created_at,
        'updated_at': o.updated_at,
        'client': user_brief(o.client),
    }


def available_transitions(o, role):
    out = []
    for (frm, to), (roles, reason_roles) in TRANSITIONS.items():
        if frm == o.status and role in roles and can_pass_guard(o, to):
            out.append({'to': to.value, 'label': to.label, 'reason_required': role in reason_roles})
    return out


def detail(o, user):
    role = MANAGER if get_role(user) in (MANAGER, 'ADMIN') else CLIENT
    mv, vr, quote, ready = quote_state(o)
    a = adapters.current_assignment(o)
    c = o.client
    return {
        **summary(o),
        'version': o.version,
        'delivery_address': o.delivery_address,
        'comment': o.comment,
        'desired_date': o.desired_date,
        'planned_date': o.planned_date,
        'reject_reason': o.reject_reason,
        'quality_profile': _ref(o.quality_profile),
        'color': _ref(o.color),
        'delivery_method': _ref(o.delivery_method, ('type',)),
        'pickup_point': _ref(o.pickup_point),
        'post_processing': [{'id': _s(p.id), 'name': p.name} for p in o.post_processings.all()],
        'client_details': {
            **user_brief(c),
            'phone': getattr(c, 'phone', ''),
            'company_name': getattr(c, 'company_name', ''),
            'client_type': getattr(c, 'client_type', 'INDIVIDUAL'),
        },
        'model': model_dto(mv),
        'quote': quote_dto(quote),
        'validation': validation_dto(vr),
        'ready': ready,
        'assignment': None if not a else {
            'printer': a.printer.name,
            'printer_id': _s(a.printer_id),
            'workshop': a.printer.workshop.name,
            'planned_start': a.planned_start,
            'planned_end': a.planned_end,
            'is_manual': a.is_manual,
            'reason': a.reason,
        },
        'events': [
            {
                'id': _s(e.id),
                'type': e.type,
                'from_status': e.from_status,
                'to_status': e.to_status,
                'reason': e.reason,
                'actor': _display_name(e.actor),
                'created_at': e.created_at,
            }
            for e in o.events.select_related('actor')
        ],
        'available_transitions': [] if o.status in {s.value for s in FINAL} else available_transitions(o, role),
        'can_edit': o.status == Status.DRAFT and role == CLIENT,
    }


def message_dto(m):
    mv_num = getattr(m, 'model_version_num', None)
    if mv_num is None and getattr(m, 'model_version', None):
        mv_num = m.model_version.version
    return {
        'id': _s(m.id),
        'author': user_brief(m.author),
        'text': m.text,
        'created_at': m.created_at,
        'model_version': mv_num,
    }
