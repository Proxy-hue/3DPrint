from django.db.models import Q
from django.http import FileResponse
from rest_framework import generics, permissions, serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Order, PrintModel
from .serializers import OrderSerializer, PrintModelSerializer


class PrintModelListCreateView(generics.ListCreateAPIView):
    serializer_class = PrintModelSerializer

    def get_queryset(self):
        return PrintModel.objects.filter(owner=self.request.user)


class PrintModelDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = PrintModelSerializer

    def get_queryset(self):
        return PrintModel.objects.filter(owner=self.request.user)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def download_model(request, pk):
    is_staff = (
        getattr(request.user, "role", None) in {"manager", "admin"}
        or request.user.is_staff
        or request.user.is_superuser
    )
    if is_staff:
        model = PrintModel.objects.filter(pk=pk).first()
    else:
        model = (
            PrintModel.objects.filter(pk=pk)
            .filter(
                Q(owner_id=request.user.pk)
                | Q(orders__owner_id=request.user.pk)
            )
            .distinct()
            .first()
        )
    if model is None:
        return Response({"detail": "Модель не найдена."}, status=404)
    model.file.open("rb")
    response = FileResponse(model.file, as_attachment=True, filename=model.original_name)
    response["Content-Length"] = model.size
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


MATERIALS = {
    "pla": {"name": "PLA", "description": "Универсальный пластик для прототипов и макетов", "pricePerGram": 3.2, "density": 1.24, "technology": "FDM", "colors": ["#f1f1ee", "#4b525c", "#ff8a3d", "#4c8df6", "#3fbf8f", "#e5484d"], "colorNames": ["Белый", "Графит", "Оранжевый", "Синий", "Зелёный", "Красный"]},
    "abs": {"name": "ABS", "description": "Прочный и термостойкий, для функциональных деталей", "pricePerGram": 3.8, "density": 1.04, "technology": "FDM", "colors": ["#f1f1ee", "#4b525c", "#ff8a3d", "#4c8df6", "#e5484d"], "colorNames": ["Белый", "Графит", "Оранжевый", "Синий", "Красный"]},
    "petg": {"name": "PETG", "description": "Ударопрочный материал с хорошей химической стойкостью", "pricePerGram": 4.1, "density": 1.27, "technology": "FDM", "colors": ["#f1f1ee", "#4b525c", "#ff8a3d", "#4c8df6", "#3fbf8f"], "colorNames": ["Белый", "Графит", "Оранжевый", "Синий", "Зелёный"]},
    "resin": {"name": "Resin", "description": "Высокая детализация и гладкая поверхность", "pricePerGram": 9.5, "density": 1.1, "technology": "SLA", "colors": ["#f1f1ee", "#4b525c", "#ff8a3d"], "colorNames": ["Белый", "Графит", "Оранжевый"]},
    "nylon": {"name": "Nylon", "description": "Износостойкий инженерный материал для сложных деталей", "pricePerGram": 8.2, "density": 1.14, "technology": "SLS", "colors": ["#f1f1ee", "#4b525c"], "colorNames": ["Белый", "Графит"]},
}


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def materials(request):
    return Response([
        {"id": material_id, **material}
        for material_id, material in MATERIALS.items()
    ])


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def calculate_price(request):
    configuration = request.data
    material = MATERIALS.get(configuration.get("materialId"))
    if not material:
        return Response({"detail": "Выбранный материал не найден."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        technology = configuration["technology"]
        layer_height = float(configuration["layerHeight"])
        infill = float(configuration["infill"])
        quantity = int(configuration["quantity"])
        dimensions = configuration["dimensions"]
        x = float(dimensions["x"])
        y = float(dimensions["y"])
        z = float(dimensions["z"])
    except (KeyError, TypeError, ValueError):
        return Response({"detail": "Некорректные параметры расчета."}, status=status.HTTP_400_BAD_REQUEST)

    if technology != material["technology"]:
        return Response({"detail": "Материал несовместим с выбранной технологией."}, status=status.HTTP_400_BAD_REQUEST)
    if not 0.1 <= layer_height <= 0.3 or not 10 <= infill <= 100:
        return Response({"detail": "Некорректная высота слоя или заполнение."}, status=status.HTTP_400_BAD_REQUEST)
    if not 1 <= quantity <= 99 or any(not 1 <= value <= 250 for value in (x, y, z)):
        return Response({"detail": "Габариты или тираж вне допустимого диапазона."}, status=status.HTTP_400_BAD_REQUEST)

    fill_factor = 1 if technology == "SLA" else 0.3 + (infill / 100) * 0.7
    volume = (x * y * z) / 1000
    estimated_weight = max(1, volume * fill_factor * material["density"] * 0.035)
    layer_factor = 0.2 / layer_height
    material_cost = estimated_weight * material["pricePerGram"] * quantity
    printing_cost = estimated_weight * 42 * layer_factor * quantity
    post_processing = configuration.get("postProcessing", "none")
    post_processing_cost = (350 if post_processing == "sanding" else 650 if post_processing == "painting" else 0) * quantity
    delivery = 390
    lead_time = max(2, (round((estimated_weight * quantity * layer_factor) / 120 + 0.499999)))

    return Response({
        "material": round(material_cost),
        "printing": round(printing_cost),
        "postProcessing": post_processing_cost,
        "delivery": delivery,
        "total": round(material_cost + printing_cost + post_processing_cost + delivery),
        "leadTimeDays": lead_time,
        "estimatedWeight": round(estimated_weight * 10) / 10,
    })


class OrderListCreateView(generics.ListCreateAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(self.request.user, "role", None) in ("manager", "admin"):
            return Order.objects.select_related("model", "owner").all()
        return Order.objects.filter(owner=self.request.user).select_related("model")

    def perform_create(self, serializer):
        configuration = serializer.validated_data["configuration"]
        try:
            price = calculate_order_price(configuration)
        except ValueError as error:
            raise serializers.ValidationError({"configuration": str(error)})
        model = serializer.validated_data["model"]
        dimensions = (model.width_mm, model.height_mm, model.depth_mm)
        equipment_compatible = all(dimension is not None and 1 <= dimension <= 250 for dimension in dimensions)
        serializer.save(
            owner=self.request.user,
            price=price,
            equipment_compatible=equipment_compatible,
        )


def calculate_order_price(configuration):
    material_id = configuration.get("material")
    material = MATERIALS.get(material_id)
    if not material:
        raise ValueError("Выбранный материал не найден.")
    technology = configuration.get("technology")
    if technology != material["technology"]:
        raise ValueError("Материал несовместим с выбранной технологией.")
    try:
        layer_height = float(configuration["layerHeight"])
        infill = float(configuration["infill"])
        quantity = int(configuration["quantity"])
        dimensions = configuration["dimensions"]
        x = float(dimensions["x"])
        y = float(dimensions["y"])
        z = float(dimensions["z"])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Некорректные параметры расчета.") from error
    if not 0.1 <= layer_height <= 0.3 or not 10 <= infill <= 100:
        raise ValueError("Некорректная высота слоя или заполнение.")
    if not 1 <= quantity <= 99 or any(not 1 <= value <= 250 for value in (x, y, z)):
        raise ValueError("Габариты или тираж вне допустимого диапазона.")
    fill_factor = 1 if technology == "SLA" else 0.3 + (infill / 100) * 0.7
    estimated_weight = max(1, ((x * y * z) / 1000) * fill_factor * material["density"] * 0.035)
    layer_factor = 0.2 / layer_height
    material_cost = estimated_weight * material["pricePerGram"] * quantity
    printing_cost = estimated_weight * 42 * layer_factor * quantity
    post_processing = configuration.get("postProcessing", "none")
    post_processing_cost = (350 if post_processing == "sanding" else 650 if post_processing == "painting" else 0) * quantity
    delivery = 390
    lead_time = max(2, round((estimated_weight * quantity * layer_factor) / 120 + 0.499999))
    return {
        "material": round(material_cost),
        "printing": round(printing_cost),
        "postProcessing": post_processing_cost,
        "delivery": delivery,
        "total": round(material_cost + printing_cost + post_processing_cost + delivery),
        "leadTimeDays": lead_time,
        "estimatedWeight": round(estimated_weight * 10) / 10,
    }


class OrderDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = OrderSerializer

    def get_queryset(self):
        if getattr(self.request.user, "role", None) in ("manager", "admin"):
            return Order.objects.select_related("model", "owner").all()
        return Order.objects.filter(owner=self.request.user).select_related("model")

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        if getattr(request.user, "role", None) not in ("manager", "admin") and "status" in request.data:
            return Response({"detail": "Только менеджер может менять статус."}, status=status.HTTP_403_FORBIDDEN)
        if "status" in request.data:
            next_status = request.data["status"]
            allowed = {choice.value for choice in Order.Status}
            if next_status not in allowed:
                return Response({"detail": "Некорректный статус."}, status=status.HTTP_400_BAD_REQUEST)
            order.status = next_status
            order.save(update_fields=("status", "updated_at"))
            return Response(OrderSerializer(order, context={"request": request}).data)
        return super().update(request, *args, **kwargs)
