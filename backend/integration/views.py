from django.http import FileResponse, HttpResponse
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import renderers, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .api import (
    IntegrationServiceError,
    export_events,
    export_load,
    export_orders,
    get_engineering_order_with_model,
    list_engineering_orders,
    render_csv,
    update_engineering_order_status,
)
from .authentication import ApiKeyAuthentication
from .contracts import (
    ENGINEERING_READ,
    ENGINEERING_WRITE,
    EXPORT_READ,
    EngineeringStatusCommand,
    ExportQuery,
)
from .permissions import HasApiScope
from .serializers import EngineeringStatusUpdateSerializer, ExportFilterSerializer


class CSVPassThroughRenderer(renderers.BaseRenderer):
    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class BaseIntegrationView(APIView):
    authentication_classes = (ApiKeyAuthentication,)
    permission_classes = (HasApiScope,)

    def handle_service_error(self, error: IntegrationServiceError) -> Response:
        return Response(
            {"code": error.code, "message": error.message},
            status=error.http_status,
        )


class IntegrationOrderListView(BaseIntegrationView):
    required_scope = ENGINEERING_READ
    serializer_class = serializers.Serializer

    @extend_schema(
        parameters=[
            OpenApiParameter(name="status", type=str, required=False, description="Фильтр по статусу (PAID…READY)"),
        ],
        responses={200: None},
    )
    def get(self, request):
        status_filter = request.query_params.get("status")
        try:
            orders = list_engineering_orders(status_filter=status_filter)
        except IntegrationServiceError as error:
            return self.handle_service_error(error)
        return Response({"count": len(orders), "results": orders}, status=status.HTTP_200_OK)


class IntegrationOrderModelDownloadView(BaseIntegrationView):
    required_scope = ENGINEERING_READ
    serializer_class = serializers.Serializer

    @extend_schema(responses={(200, "application/octet-stream"): bytes})
    def get(self, request, pk: int):
        try:
            order = get_engineering_order_with_model(pk)
        except IntegrationServiceError as error:
            return self.handle_service_error(error)

        model = order.model
        try:
            model_file = model.file.open("rb")
        except OSError:
            return Response(
                {
                    "code": "MODEL_FILE_UNAVAILABLE",
                    "message": "Файл модели временно недоступен в хранилище.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        response = FileResponse(
            model_file,
            as_attachment=True,
            filename=model.original_name,
        )
        response["Content-Length"] = model.size
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response


class IntegrationOrderStatusView(BaseIntegrationView):
    required_scope = ENGINEERING_WRITE
    serializer_class = EngineeringStatusUpdateSerializer

    @extend_schema(request=EngineeringStatusUpdateSerializer, responses={200: None})
    def post(self, request, pk: int):
        serializer = EngineeringStatusUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Некорректные параметры обновления статуса.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data
        command = EngineeringStatusCommand(
            order_id=pk,
            actor_client_id=request.user.client_id,
            target_status=validated.get("status"),
            reason=validated.get("reason", ""),
            actual_material_name=validated.get("actual_material_name"),
            actual_material_g=validated.get("actual_material_g"),
            actual_print_hours=validated.get("actual_print_hours"),
            printer_name=validated.get("printer_name"),
            notes=validated.get("notes"),
        )
        try:
            receipt = update_engineering_order_status(command)
        except IntegrationServiceError as error:
            return self.handle_service_error(error)

        return Response(
            {
                "order_id": receipt.order_id,
                "previous_status": receipt.previous_status,
                "status": receipt.status,
                "spec_status": receipt.spec_status,
                "actual_data": dict(receipt.actual_data),
                "event_id": str(receipt.event_id) if receipt.event_id else None,
                "updated_at": receipt.updated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class BaseExportView(BaseIntegrationView):
    required_scope = EXPORT_READ
    renderer_classes = (renderers.JSONRenderer, CSVPassThroughRenderer)
    export_filename = "export.csv"
    csv_columns: tuple[str, ...] = ()

    def _parse_query(self, request) -> tuple[ExportQuery | None, Response | None]:
        serializer = ExportFilterSerializer(data=request.query_params)
        if not serializer.is_valid():
            return None, Response(
                {
                    "code": "VALIDATION_ERROR",
                    "message": "Некорректные параметры фильтрации выгрузки.",
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = serializer.validated_data
        return (
            ExportQuery(
                status=data.get("status") or None,
                order_id=data.get("order_id"),
                date_from=data.get("date_from"),
                date_to=data.get("date_to"),
                horizon_days=data.get("days", 7),
            ),
            None,
        )

    def _wants_csv(self, request) -> bool:
        explicit = request.query_params.get("format")
        if explicit:
            return explicit.strip().lower() == "csv"
        accepted = getattr(request, "accepted_renderer", None)
        return getattr(accepted, "format", None) == "csv"

    def _respond(self, request, rows: list[dict]):
        if self._wants_csv(request):
            csv_body = render_csv(rows, self.csv_columns)
            response = HttpResponse(csv_body, content_type="text/csv; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{self.export_filename}"'
            response["X-Content-Type-Options"] = "nosniff"
            response["Cache-Control"] = "private, no-store"
            return response
        return Response({"count": len(rows), "results": rows}, status=status.HTTP_200_OK)


class IntegrationExportOrdersView(BaseExportView):
    serializer_class = ExportFilterSerializer
    export_filename = "orders_export.csv"
    csv_columns = (
        "order_id",
        "status",
        "spec_status",
        "owner_id",
        "model_id",
        "model_name",
        "model_format",
        "technology",
        "material",
        "quantity",
        "total_price",
        "lead_time_days",
        "estimated_weight_g",
        "equipment_compatible",
        "printer_name",
        "actual_material_name",
        "actual_material_g",
        "actual_print_hours",
        "created_at",
        "updated_at",
    )

    def get(self, request):
        query, error_response = self._parse_query(request)
        if error_response is not None:
            return error_response
        rows = export_orders(query)
        return self._respond(request, rows)


class IntegrationExportEventsView(BaseExportView):
    serializer_class = ExportFilterSerializer
    export_filename = "events_export.csv"
    csv_columns = (
        "event_id",
        "order_id",
        "actor_client",
        "event_type",
        "from_status",
        "to_status",
        "reason",
        "actual_data",
        "created_at",
    )

    def get(self, request):
        query, error_response = self._parse_query(request)
        if error_response is not None:
            return error_response
        rows = export_events(query)
        return self._respond(request, rows)


class IntegrationExportLoadView(BaseExportView):
    serializer_class = ExportFilterSerializer
    export_filename = "load_export.csv"
    csv_columns = (
        "printer_name",
        "technology",
        "horizon_days",
        "capacity_hours",
        "orders_count",
        "active_orders_count",
        "completed_orders_count",
        "planned_hours",
        "actual_print_hours",
        "actual_material_g",
        "load_percent",
        "idle_hours",
    )

    def get(self, request):
        query, error_response = self._parse_query(request)
        if error_response is not None:
            return error_response
        rows = export_load(query)
        return self._respond(request, rows)
