import io
import uuid

from django.conf import settings
from django.db import transaction
from django.db.models import Prefetch, Q
from django.http import FileResponse, Http404
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from messaging import services as messaging_services
from pricing.models import Quote

from . import adapters
from . import serializers as ser
from . import services
from .exceptions import DomainError
from .models import Order
from .permissions import ADMIN, MANAGER, IsAdminRole, IsClient, IsClientOrManager, IsManager, get_role

PAGE_SIZE = 20
ALLOWED_ORDERING = {
    'created_at': 'created_at',
    '-created_at': '-created_at',
    'priority': 'priority',
    '-priority': '-priority',
    'status': 'status',
    '-status': '-status',
    'number': 'number',
    '-number': '-number',
}


def _parse_uuid(raw, label):
    try:
        return uuid.UUID(str(raw))
    except (ValueError, TypeError):
        raise DomainError(f'Некорректный идентификатор фильтра ({label}).', 'validation')


def get_order(request, pk):
    is_mgr = get_role(request.user) in (MANAGER, ADMIN)
    base = (
        Order.objects.select_related(
            'client', 'material', 'technology', 'quality_profile',
            'color', 'delivery_method', 'pickup_point',
        ).prefetch_related('post_processings')
    )
    qs = base if is_mgr else base.filter(client=request.user)
    o = qs.filter(pk=pk).first()
    if not o:
        raise Http404
    if is_mgr and o.status == 'DRAFT':
        raise Http404
    return o


class OrderListCreate(APIView):
    permission_classes = [IsClientOrManager]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        qs = (
            Order.objects.select_related('client', 'material', 'technology')
            .prefetch_related(Prefetch('quotes', queryset=Quote.objects.filter(is_current=True)))
        )
        p = request.query_params
        if get_role(request.user) == 'CLIENT':
            qs = qs.filter(client=request.user)
        else:
            qs = qs.exclude(status='DRAFT')
        if p.get('status'):
            qs = qs.filter(status__in=[s.strip() for s in p['status'].split(',') if s.strip()])
        if p.get('priority') not in (None, ''):
            try:
                qs = qs.filter(priority=int(p['priority']))
            except ValueError:
                raise DomainError('Некорректный фильтр приоритета.', 'validation')
        if p.get('material'):
            qs = qs.filter(material_id=_parse_uuid(p['material'], 'material'))
        if p.get('workshop'):
            wid = _parse_uuid(p['workshop'], 'workshop')
            if hasattr(Order, 'assignments'):
                qs = qs.filter(assignments__is_current=True, assignments__printer__workshop_id=wid)
        if p.get('date_from'):
            df = parse_date(p['date_from'])
            if not df:
                raise DomainError('Некорректная дата начала периода.', 'validation')
            qs = qs.filter(created_at__date__gte=df)
        if p.get('date_to'):
            dt = parse_date(p['date_to'])
            if not dt:
                raise DomainError('Некорректная дата окончания периода.', 'validation')
            qs = qs.filter(created_at__date__lte=dt)
        if p.get('q'):
            qs = qs.filter(
                Q(number__icontains=p['q'])
                | Q(client__email__icontains=p['q'])
                | Q(client__first_name__icontains=p['q'])
                | Q(client__last_name__icontains=p['q'])
            )
        ordering = ALLOWED_ORDERING.get(p.get('ordering') or '-created_at', '-created_at')
        qs = qs.distinct().order_by(ordering, '-created_at')
        try:
            page = max(int(p.get('page', 1)), 1)
        except ValueError:
            raise DomainError('Номер страницы должен быть целым числом.', 'validation')
        total = qs.count()
        items = qs[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
        return Response({
            'count': total,
            'page': page,
            'page_size': PAGE_SIZE,
            'results': [ser.summary(o) for o in items],
        })

    def post(self, request):
        if get_role(request.user) != 'CLIENT':
            raise DomainError('Создавать заказы могут только клиенты.', 'forbidden', 403)
        f = request.FILES.get('file') if hasattr(request, 'FILES') else None
        if f is not None:
            if f.size > getattr(settings, 'MAX_UPLOAD_BYTES', 50 * 1024 * 1024):
                raise DomainError('E-01: Размер файла превышает 50 МБ.', 'E-01')
            raw = f.read()
            adapters.check_upload_prevalidate(f.name, raw)
            with transaction.atomic():
                o = services.create_draft(request.user)
                services.attach_model(o, request.user, f.name, raw)
            o.refresh_from_db()
            return Response(ser.detail(o, request.user), status=201)
        o = services.create_draft(request.user, request.data if request.data else None)
        return Response(ser.detail(o, request.user), status=201)


class OrderDetail(APIView):
    permission_classes = [IsClientOrManager]

    def get(self, request, pk):
        o = get_order(request, pk)
        return Response(ser.detail(o, request.user))

    def patch(self, request, pk):
        o = get_order(request, pk)
        services.update_draft(o, request.user, request.data)
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))


class ModelUpload(APIView):
    permission_classes = [IsClient]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        o = get_order(request, pk)
        f = request.FILES.get('file')
        if not f:
            raise DomainError('E-01: Файл не передан.', 'E-01')
        if f.size > getattr(settings, 'MAX_UPLOAD_BYTES', 50 * 1024 * 1024):
            raise DomainError('E-01: Размер файла превышает 50 МБ.', 'E-01')
        mv = services.attach_model(o, request.user, f.name, f.read())
        o.refresh_from_db()
        return Response({'model': ser.model_dto(mv), 'order': ser.detail(o, request.user)}, status=201)


class ModelFile(APIView):
    permission_classes = [IsClientOrManager]

    def get(self, request, pk, v):
        o = get_order(request, pk)
        mv = adapters.get_model_version(o, v)
        if not mv:
            raise Http404
        return Response(adapters.model_file_info(o, mv))


class ModelDownload(APIView):
    permission_classes = [IsClientOrManager]

    def get(self, request, pk, v):
        o = get_order(request, pk)
        mv = adapters.get_model_version(o, v)
        if not mv:
            raise Http404
        return FileResponse(io.BytesIO(adapters.read_model_bytes(mv)), as_attachment=True, filename=mv.file_name)


class OrderQuote(APIView):
    """GET: текущий расчёт и результат проверки (спец. 5.3.4, F-CLI-06). POST: пересчёт."""

    permission_classes = [IsClientOrManager]

    def get(self, request, pk):
        o = get_order(request, pk)
        _, vr, quote, ready = services.quote_state(o)
        return Response({
            'quote': ser.quote_dto(quote),
            'validation': ser.validation_dto(vr),
            'ready': ready,
        })

    def post(self, request, pk):
        o = get_order(request, pk)
        q = services.manual_recalculate(o, request.user)
        return Response(ser.quote_dto(q))


class OrderConfirm(APIView):
    permission_classes = [IsClient]

    def post(self, request, pk):
        o = get_order(request, pk)
        services.confirm(o, request.user)
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))


class OrderPay(APIView):
    permission_classes = [IsClient]

    def post(self, request, pk):
        o = get_order(request, pk)
        services.pay(o, request.user)
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))


class OrderCancel(APIView):
    permission_classes = [IsClientOrManager]

    def post(self, request, pk):
        o = get_order(request, pk)
        services.cancel(o, request.user, request.data.get('reason', ''))
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))


class OrderRepeat(APIView):
    permission_classes = [IsClient]

    def post(self, request, pk):
        o = get_order(request, pk)
        new_o = services.repeat(o, request.user)
        return Response(ser.detail(new_o, request.user), status=201)


class OrderDecision(APIView):
    permission_classes = [IsManager]

    def post(self, request, pk):
        o = get_order(request, pk)
        services.decision(o, request.user, request.data.get('action'), request.data.get('reason', ''))
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))


class OrderStatus(APIView):
    permission_classes = [IsManager]

    def post(self, request, pk):
        o = get_order(request, pk)
        target = request.data.get('status') or request.data.get('to')
        services.change_status(o, request.user, target, request.data.get('reason', ''))
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))


class OrderPriority(APIView):
    permission_classes = [IsManager]

    def post(self, request, pk):
        o = get_order(request, pk)
        services.set_priority(o, request.user, request.data.get('priority'))
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))


class OrderAdjustment(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        o = get_order(request, pk)
        raw_adj = request.data.get('adjustment')
        if raw_adj is None or raw_adj == '':
            raise DomainError('Укажите сумму корректировки.', 'validation')
        services.adjust_price(o, request.user, raw_adj, request.data.get('reason', ''))
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))


class OrderMessages(APIView):
    permission_classes = [IsClientOrManager]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        o = get_order(request, pk)
        since = None
        raw_since = request.query_params.get('since')
        if raw_since:
            since = parse_datetime(raw_since)
            if not since:
                raise DomainError('Некорректный формат параметра since.', 'validation')
            if timezone.is_naive(since):
                since = timezone.make_aware(since)
        return Response([ser.message_dto(m) for m in messaging_services.list_for(o, since=since)])

    def post(self, request, pk):
        o = get_order(request, pk)
        f = request.FILES.get('file') if hasattr(request, 'FILES') else None
        if f and f.size > getattr(settings, 'MAX_UPLOAD_BYTES', 50 * 1024 * 1024):
            raise DomainError('E-01: Размер файла превышает 50 МБ.', 'E-01')
        msg = services.post_message(
            o, request.user, request.data.get('text', ''),
            f.name if f else None, f.read() if f else None,
        )
        return Response(ser.message_dto(msg), status=201)


class OrderRecommendation(APIView):
    permission_classes = [IsManager]

    def get(self, request, pk):
        o = get_order(request, pk)
        return Response(services.recommendation(o))


class OrderAssignment(APIView):
    permission_classes = [IsManager]

    def post(self, request, pk):
        o = get_order(request, pk)
        services.assign_printer(o, request.user, request.data.get('printer_id'), request.data.get('reason', ''))
        o.refresh_from_db()
        return Response(ser.detail(o, request.user))
