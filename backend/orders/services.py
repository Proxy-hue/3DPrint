"""Оркестрация заказов: FSM (14 статусов), валидация/расчёт, решения менеджера, аудит.

Взаимодействие с модулями `catalog`, `pricing`, `messaging`, `notifications`, `payment`
идёт через их публичные интерфейсы; модули `models_app`, `validation`, `scheduling`
подключаются через адаптер `orders.adapters`.
"""
import datetime
import logging

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from django.utils.dateparse import parse_date

from catalog import audit as catalog_audit
from catalog import models as catalog_models
from notifications import services as notification_services
from payment import services as payment_services
from pricing import services as pricing_services
from messaging import services as messaging_services

from . import adapters
from .exceptions import DomainError
from .models import Order, OrderEvent, OrderPostProcessing, Status
from .permissions import ADMIN, CLIENT, MANAGER, get_role
from .tasks import enqueue

logger = logging.getLogger(__name__)
S = Status
SYSTEM, INTEGRATION = 'SYSTEM', 'INTEGRATION'
FINAL = {S.COMPLETED, S.REJECTED, S.CANCELLED}

TRANSITIONS = {
    (S.DRAFT, S.NEW): ({CLIENT}, set()),
    (S.DRAFT, S.CANCELLED): ({CLIENT}, set()),
    (S.NEW, S.CHECKED): ({SYSTEM}, set()),
    (S.NEW, S.MANUAL_REVIEW): ({SYSTEM}, set()),
    (S.MANUAL_REVIEW, S.CHECKED): ({MANAGER}, set()),
    (S.MANUAL_REVIEW, S.CLARIFICATION): ({MANAGER}, {MANAGER}),
    (S.MANUAL_REVIEW, S.REJECTED): ({MANAGER}, {MANAGER}),
    (S.CHECKED, S.CLARIFICATION): ({MANAGER}, {MANAGER}),
    (S.CHECKED, S.REJECTED): ({MANAGER}, {MANAGER}),
    (S.CHECKED, S.AWAITING_PAYMENT): ({MANAGER}, set()),
    (S.CLARIFICATION, S.NEW): ({CLIENT, SYSTEM}, set()),
    (S.CLARIFICATION, S.REJECTED): ({MANAGER}, {MANAGER}),
    (S.AWAITING_PAYMENT, S.PAID): ({CLIENT, SYSTEM}, set()),
    (S.PAID, S.DISTRIBUTED): ({MANAGER}, set()),
    (S.DISTRIBUTED, S.PRINTING): ({MANAGER, INTEGRATION}, set()),
    (S.PRINTING, S.POST_PROCESSING): ({MANAGER, INTEGRATION}, set()),
    (S.PRINTING, S.READY): ({MANAGER, INTEGRATION}, set()),
    (S.POST_PROCESSING, S.READY): ({MANAGER}, set()),
    (S.READY, S.COMPLETED): ({MANAGER}, set()),
}
for _st in (S.NEW, S.CHECKED, S.MANUAL_REVIEW, S.CLARIFICATION, S.AWAITING_PAYMENT):
    TRANSITIONS[(_st, S.CANCELLED)] = ({CLIENT, MANAGER}, {MANAGER})
for _st in (S.PAID, S.DISTRIBUTED):
    TRANSITIONS[(_st, S.CANCELLED)] = ({MANAGER}, {MANAGER})


def err(msg, code='error', status=400):
    return DomainError(msg, code=code, status=status)


def norm_role(user, explicit_role=None):
    if explicit_role in (SYSTEM, INTEGRATION):
        return explicit_role
    if user is None:
        return SYSTEM
    r = get_role(user)
    return MANAGER if r in (MANAGER, ADMIN) else CLIENT


def _managers():
    User = get_user_model()
    return User.objects.filter(role__in=(MANAGER, ADMIN), is_active=True)


def event(order, ev_type, actor=None, from_status='', to_status='', reason='', payload=None):
    return OrderEvent.objects.create(
        order=order, actor=actor, type=ev_type,
        from_status=from_status or '', to_status=to_status or '',
        reason=reason or '', payload=payload or {},
    )


def _bump(order, **fields):
    """Оптимистичная блокировка: обновление только если version не изменилась."""
    n = Order.objects.filter(pk=order.pk, version=order.version).update(
        version=F('version') + 1, updated_at=timezone.now(), **fields,
    )
    if not n:
        raise err('Заказ был изменён другим пользователем. Обновите страницу.', 'version_conflict', 409)
    order.version += 1
    for k, v in fields.items():
        setattr(order, k, v)


def _check_access(order, user, role):
    if role == CLIENT and user is not None and order.client_id != user.id:
        raise err('Заказ не найден.', 'not_found', 404)


def _lock_order(order):
    """Берёт пессимистичную блокировку строки заказа и обновляет поля в памяти."""
    locked = Order.objects.select_for_update().filter(pk=order.pk).first()
    if not locked:
        raise err('Заказ не найден.', 'not_found', 404)
    order.refresh_from_db()


def can_pass_guard(order, to) -> bool:
    to = S(to)
    frm = S(order.status)
    if (frm, to) == (S.PAID, S.DISTRIBUTED) and not adapters.current_assignment(order):
        return False
    if (frm, to) == (S.PRINTING, S.POST_PROCESSING) and not order.post_processings.exists():
        return False
    if (frm, to) == (S.PRINTING, S.READY) and order.post_processings.exists():
        return False
    if (frm, to) == (S.CHECKED, S.AWAITING_PAYMENT) and not pricing_services.current_quote(order):
        return False
    return True


def _guard(order, to):
    if (order.status, to) == (S.PAID, S.DISTRIBUTED) and not adapters.current_assignment(order):
        raise err('Сначала назначьте принтер.', 'no_assignment', 409)
    if (order.status, to) == (S.PRINTING, S.POST_PROCESSING) and not order.post_processings.exists():
        raise err('Постобработка не выбрана — переходите сразу в «Готов к выдаче».', 'guard', 409)
    if (order.status, to) == (S.PRINTING, S.READY) and order.post_processings.exists():
        raise err('Выбрана постобработка — сначала переведите заказ в «Постобработка».', 'guard', 409)
    if (order.status, to) == (S.CHECKED, S.AWAITING_PAYMENT) and not pricing_services.current_quote(order):
        raise err('Невозможно отправить заказ на оплату без расчёта стоимости.', 'no_quote', 409)


NOTIFY_CLIENT = {
    S.CHECKED, S.CLARIFICATION, S.AWAITING_PAYMENT, S.PAID, S.DISTRIBUTED,
    S.PRINTING, S.POST_PROCESSING, S.READY, S.COMPLETED, S.REJECTED,
    S.CANCELLED, S.MANUAL_REVIEW,
}


def transition(order, to, *, user=None, role=None, reason='', payload=None):
    role = norm_role(user, role)
    _check_access(order, user, role)
    try:
        to = S(to)
    except ValueError:
        raise err(f'Неизвестный статус «{to}».', 'validation', 400)
    rule = TRANSITIONS.get((S(order.status), to))
    if not rule:
        raise err(f'Переход «{S(order.status).label}» → «{to.label}» недопустим.', 'invalid_transition', 409)
    roles, reason_roles = rule
    if role not in roles:
        raise err('Недостаточно прав для этого перехода.', 'forbidden', 403)
    if role in reason_roles and not (reason or '').strip():
        raise err('Необходимо указать причину.', 'reason_required', 400)
    _guard(order, to)
    prev = order.status
    extra = {}
    if to == S.REJECTED:
        extra['reject_reason'] = reason
    _bump(order, status=to.value, **extra)
    if to in (S.CANCELLED, S.REJECTED):
        adapters.clear_assignment(order)
    event(order, 'STATUS_CHANGED', user, prev, to.value, reason, payload)
    if to in NOTIFY_CLIENT and role != CLIENT:
        text = f'Заказ {order.number}: статус изменён на «{to.label}».'
        if reason and to in (S.REJECTED, S.CLARIFICATION, S.CANCELLED):
            text += f' {reason}'
        notification_services.notify(order.client, text, order)
    if to in (S.MANUAL_REVIEW, S.PAID) or (prev == S.CLARIFICATION and to == S.NEW):
        for m in _managers():
            notification_services.notify(m, f'Заказ {order.number}: «{to.label}».', order)
    return order


# ---------- Черновик и параметры ----------
def _next_number():
    today = timezone.localdate()
    prefix = f'3DP-{today:%y%m%d}-'
    last = Order.objects.filter(number__startswith=prefix).order_by('-number').first()
    seq = 1
    if last:
        try:
            seq = int(last.number.rsplit('-', 1)[-1]) + 1
        except ValueError:
            seq = Order.objects.filter(created_at__date=today).count() + 1
    return f'{prefix}{seq:04d}'


PARAM_MODELS = {
    'technology': (catalog_models.Technology, True),
    'material': (catalog_models.Material, True),
    'quality_profile': (catalog_models.QualityProfile, True),
    'color': (catalog_models.Color, True),
    'delivery_method': (catalog_models.DeliveryMethod, True),
    'pickup_point': (catalog_models.PickupPoint, True),
}
PARAM_FIELDS = tuple(PARAM_MODELS.keys())


def desired_date_ok(d):
    return d is None or d >= timezone.localdate()


@transaction.atomic
def create_draft(client, data=None):
    order = None
    for _ in range(10):
        try:
            with transaction.atomic():
                order = Order.objects.create(client=client, number=_next_number(), status=S.DRAFT)
            break
        except IntegrityError:
            continue
    if not order:
        raise err('Не удалось сформировать номер заказа.')
    event(order, 'CREATED', client, '', S.DRAFT)
    if data:
        update_draft(order, client, data, recalc=False)
    return order


@transaction.atomic
def update_draft(order, user, data, recalc=True):
    if order.status != S.DRAFT:
        raise err('Редактировать можно только черновик.', 'not_draft', 409)
    _check_access(order, user, CLIENT)
    ver = data.get('version')
    if ver is not None:
        try:
            ver_int = int(ver)
        except (TypeError, ValueError):
            raise err('Некорректная версия заказа.', 'validation')
        if ver_int != order.version:
            raise err('Заказ был изменён в другом окне. Обновите страницу.', 'version_conflict', 409)

    fields = {}
    if 'quantity' in data:
        try:
            qty = int(data['quantity'])
        except (TypeError, ValueError):
            raise err('Количество должно быть целым числом.', 'validation')
        if qty < 1:
            raise err('Количество должно быть не меньше 1.', 'validation')
        fields['quantity'] = qty
    if 'delivery_address' in data:
        fields['delivery_address'] = str(data['delivery_address'] or '').strip()[:255]
    if 'comment' in data:
        fields['comment'] = str(data['comment'] or '')
    if 'desired_date' in data:
        raw_d = data['desired_date']
        if not raw_d:
            fields['desired_date'] = None
        else:
            d = raw_d if isinstance(raw_d, datetime.date) else parse_date(str(raw_d))
            if not d:
                raise err('Некорректный формат желаемой даты.', 'validation')
            if not desired_date_ok(d):
                raise err('Желаемая дата не может быть в прошлом.', 'validation')
            fields['desired_date'] = d
    for key, (model_cls, has_active) in PARAM_MODELS.items():
        if key in data:
            val = data[key]
            if not val:
                fields[key + '_id'] = None
            else:
                qs = model_cls.objects.filter(pk=val)
                if has_active:
                    qs = qs.filter(is_active=True)
                try:
                    obj = qs.first()
                except Exception:
                    obj = None
                if not obj:
                    raise err(f'Недопустимое или неактивное значение справочника ({key}).', 'validation')
                fields[key + '_id'] = obj.pk

    if fields or 'post_processing' in data:
        _bump(order, **fields)

    if 'post_processing' in data:
        raw_pps = data['post_processing'] or []
        if not isinstance(raw_pps, (list, tuple)):
            raise err('Список опций постобработки должен быть массивом.', 'validation')
        pp_ids = list(dict.fromkeys(str(pid) for pid in raw_pps))
        valid_pps = []
        for pid in pp_ids:
            try:
                p_obj = catalog_models.PostProcessing.objects.filter(pk=pid, is_active=True).first()
            except Exception:
                p_obj = None
            if not p_obj:
                raise err('Выбрана недействительная опция постобработки.', 'validation')
            valid_pps.append(p_obj)
        OrderPostProcessing.objects.filter(order=order).delete()
        for p_obj in valid_pps:
            OrderPostProcessing.objects.create(order=order, post_processing=p_obj)

    if recalc:
        process_order(order.pk)
    return order


@transaction.atomic
def attach_model(order, user, file_name, data):
    _lock_order(order)
    if order.status not in (S.DRAFT, S.CLARIFICATION):
        raise err('Загрузить модель можно только в черновике или при уточнении.', 'bad_status', 409)
    _check_access(order, user, CLIENT)
    mv = adapters.add_model_version(order, file_name, data)
    if order.status == S.CLARIFICATION:
        transition(order, S.NEW, user=user, reason=f'Загружена новая версия модели (v{mv.version})')
    enqueue_process(order.pk)
    return mv


# ---------- Валидация и расчёт ----------
@transaction.atomic
def process_order(order_id):
    """Валидация + расчёт (+ автопереход NEW → CHECKED/MANUAL_REVIEW)."""
    order = (
        Order.objects.select_for_update(of=('self',))
        .select_related(
            'technology', 'material', 'quality_profile', 'color',
            'delivery_method', 'pickup_point', 'client',
        )
        .filter(pk=order_id)
        .first()
    )
    if not order:
        return None
    mv = adapters.current_model_version(order)
    if not mv:
        return None
    try:
        with transaction.atomic():
            vr = adapters.validate_order_model(order, mv)
            quote = None
            try:
                quote = pricing_services.calculate(order, mv, needs_support=vr.needs_support)
            except (pricing_services.QuoteError, DomainError):
                quote = None
            if order.status == S.NEW:
                if vr.verdict != 'ERROR' and quote:
                    transition(order, S.CHECKED, role=SYSTEM)
                else:
                    transition(order, S.MANUAL_REVIEW, role=SYSTEM)
            return vr, quote
    except Exception as exc:
        logger.exception('Ошибка при автоматической проверке/расчёте заказа %s: %s', order.number, exc)
        order.refresh_from_db()
        if order.status == S.NEW:
            transition(order, S.MANUAL_REVIEW, role=SYSTEM, reason='Ошибка автоматической обработки')
        return None


def manual_recalculate(order, user):
    res = process_order(order.pk)
    if not res or not res[1]:
        raise err('Недостаточно данных для расчёта (проверьте модель и параметры).')
    return res[1]


def quote_state(order):
    mv = adapters.current_model_version(order)
    vr = adapters.latest_validation(order, mv) if mv else None
    quote = pricing_services.current_quote(order)
    return mv, vr, quote, bool(mv and vr)


# ---------- Действия клиента ----------
@transaction.atomic
def confirm(order, user):
    _lock_order(order)
    _check_access(order, user, CLIENT)
    if order.status != S.DRAFT:
        raise err('Подтвердить можно только черновик.', 'not_draft', 409)
    mv = adapters.current_model_version(order)
    if not mv:
        raise err('Загрузите 3D-модель.', 'no_model')
    missing = [
        name for name, val in (
            ('технология', order.technology_id),
            ('материал', order.material_id),
            ('качество', order.quality_profile_id),
            ('цвет', order.color_id),
            ('способ получения', order.delivery_method_id),
        ) if not val
    ]
    if missing:
        raise err('Не заполнено: ' + ', '.join(missing) + '.', 'incomplete')
    if order.delivery_method.type == 'PICKUP' and not order.pickup_point_id:
        raise err('Выберите пункт выдачи.', 'incomplete')
    if order.delivery_method.type == 'COURIER' and not (order.delivery_address or '').strip():
        raise err('Укажите адрес доставки.', 'incomplete')
    if not desired_date_ok(order.desired_date):
        raise err('Желаемая дата не может быть в прошлом.', 'validation')
    transition(order, S.NEW, user=user)
    enqueue_process(order.pk)
    return order


def enqueue_process(order_id):
    enqueue('orders.services.process_order', str(order_id))


@transaction.atomic
def cancel(order, user, reason=''):
    _lock_order(order)
    return transition(order, S.CANCELLED, user=user, reason=reason)


@transaction.atomic
def pay(order, user):
    _lock_order(order)
    role = norm_role(user)
    if role != CLIENT:
        raise err('Оплатить заказ может только клиент.', 'forbidden', 403)
    _check_access(order, user, role)
    if order.status != S.AWAITING_PAYMENT:
        raise err('Оплата доступна только для заказов в статусе «Ожидает оплаты».', 'bad_status', 409)
    quote = pricing_services.current_quote(order)
    if not quote:
        raise err('Расчёт стоимости для заказа отсутствует.', 'no_quote', 409)
    payment_services.pay(order, quote.total)
    return transition(order, S.PAID, user=user)


@transaction.atomic
def repeat(order, user):
    _check_access(order, user, CLIENT)
    new = create_draft(user)
    active = {
        k: obj for k in PARAM_FIELDS
        if (obj := getattr(order, k, None)) is not None and getattr(obj, 'is_active', True)
    }
    if 'technology' not in active:
        active.pop('material', None)
        active.pop('quality_profile', None)
    if 'material' not in active:
        active.pop('color', None)
    if 'delivery_method' not in active:
        active.pop('pickup_point', None)
    fields = {f'{k}_id': obj.pk for k, obj in active.items()}
    fields.update(quantity=order.quantity, delivery_address=order.delivery_address, comment=order.comment)
    _bump(new, **fields)
    new.refresh_from_db()
    for pp in order.post_processings.filter(is_active=True):
        OrderPostProcessing.objects.create(order=new, post_processing=pp)
    adapters.clone_model_version(order, new)
    event(new, 'REPEATED', user, payload={'source': str(order.pk)})
    process_order(new.pk)
    return new


# ---------- Переписка ----------
@transaction.atomic
def post_message(order, user, text, file_name=None, file_bytes=None):
    _lock_order(order)
    role = norm_role(user)
    _check_access(order, user, role)
    text = (text or '').strip()
    if not text and file_bytes is None:
        raise err('Введите текст сообщения или приложите модель.', 'validation')
    mv = None
    if file_bytes is not None:
        if order.status not in (S.DRAFT, S.CLARIFICATION, S.MANUAL_REVIEW):
            raise err('В текущем статусе новую версию модели загрузить нельзя.', 'bad_status', 409)
        mv = adapters.add_model_version(order, file_name or 'model.stl', file_bytes)
        text = text or f'Загружена новая версия модели (v{mv.version}).'
    msg = messaging_services.post(order, user, text, mv)
    event(order, 'MESSAGE', user, payload={'model_version': mv.version if mv else None})
    if role == CLIENT:
        if order.status != S.DRAFT:
            for m in _managers():
                notification_services.notify(m, f'Заказ {order.number}: новое сообщение от клиента.', order)
        if order.status == S.CLARIFICATION:
            transition(order, S.NEW, user=user)
            enqueue_process(order.pk)
        elif mv is not None:
            enqueue_process(order.pk)
    else:
        notification_services.notify(order.client, f'Заказ {order.number}: новое сообщение от менеджера.', order)
        if mv is not None:
            enqueue_process(order.pk)
    return msg


# ---------- Решения менеджера / администратора ----------
@transaction.atomic
def decision(order, user, action, reason=''):
    _lock_order(order)
    st = S(order.status)
    if action == 'approve':
        quote = pricing_services.current_quote(order)
        if st == S.MANUAL_REVIEW:
            if (
                not quote and order.technology_id and order.material_id
                and order.quality_profile_id and order.delivery_method_id
            ):
                mv = adapters.current_model_version(order)
                if mv and (mv.volume_cm3 or 0) > 0:
                    vr = adapters.latest_validation(order, mv)
                    quote = pricing_services.calculate(
                        order, mv, needs_support=bool(vr and vr.needs_support),
                    )
            if not quote:
                raise err('Невозможно одобрить заказ без расчёта стоимости.', 'no_quote', 409)
            transition(order, S.CHECKED, user=user, reason=reason)
        elif st == S.CHECKED:
            if not quote:
                raise err('Невозможно отправить заказ на оплату без расчёта стоимости.', 'no_quote', 409)
            transition(order, S.AWAITING_PAYMENT, user=user, reason=reason)
            if not payment_services.stub_enabled():
                payment_services.pay(order, quote.total)
                transition(order, S.PAID, role=SYSTEM, reason='Автооплата (заглушка отключена)')
        else:
            raise err('Одобрение возможно из статусов «Ручная проверка» и «Проверен».', 'invalid_transition', 409)
    elif action == 'reject':
        transition(order, S.REJECTED, user=user, reason=reason)
    elif action == 'clarify':
        transition(order, S.CLARIFICATION, user=user, reason=reason)
        messaging_services.post(order, user, reason)
    else:
        raise err('Неизвестное решение.', 'validation')
    return order


@transaction.atomic
def change_status(order, user, to, reason=''):
    _lock_order(order)
    transition(order, to, user=user, reason=reason)
    if order.status == S.AWAITING_PAYMENT and not payment_services.stub_enabled():
        quote = pricing_services.current_quote(order)
        if quote:
            payment_services.pay(order, quote.total)
            transition(order, S.PAID, role=SYSTEM, reason='Автооплата (заглушка отключена)')
    return order


@transaction.atomic
def set_priority(order, user, priority):
    if get_role(user) not in (MANAGER, ADMIN):
        raise err('Недостаточно прав.', 'forbidden', 403)
    _lock_order(order)
    try:
        p = int(priority)
    except (TypeError, ValueError):
        raise err('Приоритет должен быть целым числом (0 или 1).', 'validation')
    if p not in (0, 1):
        raise err('Допустимые значения приоритета: 0 (обычный), 1 (высокий).', 'validation')
    _bump(order, priority=p)
    event(order, 'PRIORITY_CHANGED', user, payload={'priority': p})
    return order


def recommendation(order):
    mv = adapters.current_model_version(order)
    quote = pricing_services.current_quote(order)
    if not (mv and quote and order.technology and order.material):
        raise err('Недостаточно данных для рекомендации принтера.')
    bbox = [mv.bbox_x, mv.bbox_y, mv.bbox_z]
    return adapters.recommend_printers(
        technology=order.technology, material=order.material, color=order.color,
        bbox=bbox, print_hours=quote.print_hours, exclude_order=order,
    )


@transaction.atomic
def assign_printer(order, user, printer_id, reason=''):
    _lock_order(order)
    if order.status not in (S.PAID, S.DISTRIBUTED):
        raise err('Назначение принтера возможно для заказов в статусах «Оплачен» и «Распределён».', 'bad_status', 409)
    if not printer_id:
        raise err('Укажите принтер.', 'validation')
    rec = recommendation(order)
    pid = str(printer_id)
    top_ids = [r['printer_id'] for r in rec['top']]
    all_ids = top_ids + [r['printer_id'] for r in rec['others']]
    if pid not in all_ids:
        ex = next((e for e in rec.get('excluded', []) if str(e.get('printer_id')) == pid), None)
        why = (
            ex.get('reason') or ', '.join(str(x) for x in (ex.get('reasons') or ()))
            if ex
            else ''
        )
        if why:
            raise err(f'Принтер не подходит: {why}', 'printer_ineligible')
        raise err('Принтер не найден среди подходящих.', 'printer_ineligible')
    manual = pid not in top_ids
    if manual and not (reason or '').strip():
        raise err('Для выбора принтера вне тройки рекомендаций укажите причину.', 'reason_required')
    printer = adapters.get_printer(pid)
    quote = pricing_services.current_quote(order)
    a = adapters.assign_printer_job(
        order=order, printer=printer, print_hours=quote.print_hours,
        actor_reason=reason, is_manual=manual,
    )
    _bump(order, planned_date=a.planned_end.date())
    event(order, 'ASSIGNED', user, reason=reason, payload={'printer': printer.name, 'manual': manual})
    if order.status == S.PAID:
        transition(order, S.DISTRIBUTED, user=user)
    return a


@transaction.atomic
def adjust_price(order, user, amount, reason):
    if get_role(user) != ADMIN:
        raise err('Корректировка цены доступна только администратору.', 'forbidden', 403)
    if not (reason or '').strip():
        raise err('Укажите причину корректировки.', 'reason_required')
    _lock_order(order)
    if order.status not in (S.MANUAL_REVIEW, S.CHECKED, S.CLARIFICATION):
        raise err('Корректировка возможна до отправки на оплату.', 'bad_status', 409)
    before = pricing_services.current_quote(order)
    if not before:
        raise err('Расчёт отсутствует.', 'no_quote', 409)
    before_total, before_adj = str(before.total), str(before.adjustment)
    q = pricing_services.apply_adjustment(order, amount)
    event(
        order, 'PRICE_ADJUSTED', user, reason=reason,
        payload={'adjustment': str(q.adjustment), 'total': str(q.total)},
    )
    catalog_audit.record(
        user, q, 'UPDATE',
        {'total': before_total, 'adjustment': before_adj},
        {'total': str(q.total), 'adjustment': str(q.adjustment), 'reason': reason},
    )
    return q
