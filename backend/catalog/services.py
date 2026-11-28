"""Публичный интерфейс модуля catalog (слой services).

Другие модули (validation, pricing, scheduling) обращаются к каталогу
только через эти функции и структуры из ``catalog.dto``.
"""
from . import rules
from .dto import (
    MaterialSpec, ModelInfo, PostProcessingRule, PrinterSpec,
    PRINTER_ACTIVE, default_tariff_params,
)
from .models import (
    DeliveryMethod, Material, PickupPoint, PostProcessing, Printer,
    QualityProfile, TariffVersion,
)


def get_tariff_params():
    """Параметры расчёта: значения по умолчанию + активная версия."""
    params = default_tariff_params()
    active = TariffVersion.objects.filter(is_active=True).first()
    if active is not None:
        params.update(active.params)
    return params


def get_active_tariff_version():
    return TariffVersion.objects.filter(is_active=True).first()


def get_material_spec(material_id):
    material = Material.objects.prefetch_related(
        'technologies', 'colors'
    ).get(pk=material_id)
    return MaterialSpec(
        id=str(material.pk),
        technology_ids=frozenset(str(t.pk) for t in material.technologies.all()),
        color_ids=frozenset(str(c.pk) for c in material.colors.all()),
        required_specialization=material.required_specialization,
        price_per_gram=float(material.price_per_gram),
        density=material.density,
    )


def get_printer_specs(include_inactive=False):
    """Принтеры как неизменяемые структуры (по умолчанию только ACTIVE)."""
    queryset = Printer.objects.select_related(
        'workshop'
    ).prefetch_related('materials')
    if not include_inactive:
        queryset = queryset.filter(status=PRINTER_ACTIVE)
    return [
        PrinterSpec(
            id=str(p.pk),
            name=p.name,
            workshop_id=str(p.workshop_id),
            workshop_name=p.workshop.name,
            is_main_workshop=p.workshop.is_main,
            technology_id=str(p.technology_id),
            dims_mm=(p.max_x, p.max_y, p.max_z),
            specialization=p.specialization,
            status=p.status,
            material_ids=frozenset(str(m.pk) for m in p.materials.all()),
        )
        for p in queryset
    ]


def _post_rule(post):
    return PostProcessingRule(
        code=post.code,
        incompatible_technology_ids=frozenset(
            str(t.pk) for t in post.incompatible_technologies.all()
        ),
        forbids_transparent=post.forbids_transparent,
        requires_multibody_3mf=post.requires_multibody_3mf,
    )


def check_compatibility(
    *, technology, material, quality_profile, color,
    post_processings=(), delivery_method=None, pickup_point=None,
    model_format=None, body_count=None,
):
    """Проверка сочетания параметров заказа (код E-05).

    Принимает объекты моделей, возвращает список ``CompatibilityIssue``.
    """
    return rules.check_compatibility(
        technology_id=str(technology.pk),
        material_technology_ids=frozenset(
            str(t.pk) for t in material.technologies.all()
        ),
        material_color_ids=frozenset(
            str(c.pk) for c in material.colors.all()
        ),
        color_id=str(color.pk),
        color_is_transparent=color.is_transparent,
        quality_technology_id=str(quality_profile.technology_id),
        post_processings=[_post_rule(p) for p in post_processings],
        delivery_type=delivery_method.type if delivery_method else None,
        pickup_point_active=(
            bool(pickup_point.is_active) if pickup_point else None
        ),
        model=ModelInfo(format=model_format, body_count=body_count),
    )


def build_compatibility_matrix():
    """Правила совместимости для интерфейса (GET /api/catalog/compatibility)."""
    materials = Material.objects.filter(is_active=True).prefetch_related(
        'technologies', 'colors'
    )
    posts = PostProcessing.objects.filter(is_active=True).prefetch_related(
        'incompatible_technologies'
    )
    methods = DeliveryMethod.objects.filter(is_active=True)
    points = PickupPoint.objects.filter(is_active=True)
    profiles = QualityProfile.objects.filter(is_active=True)
    return {
        'materials': [
            {
                'id': m.pk,
                'technologies': sorted(t.pk for t in m.technologies.all()),
                'colors': sorted(c.pk for c in m.colors.all()),
            }
            for m in materials
        ],
        'quality_profiles': [
            {'id': q.pk, 'technology': q.technology_id} for q in profiles
        ],
        'post_processing': [
            {
                'id': p.pk,
                'code': p.code,
                'incompatible_technologies': sorted(
                    t.pk for t in p.incompatible_technologies.all()
                ),
                'forbids_transparent': p.forbids_transparent,
                'requires_multibody_3mf': p.requires_multibody_3mf,
            }
            for p in posts
        ],
        'delivery_methods': [
            {
                'id': d.pk,
                'type': d.type,
                'pickup_points': [
                    pt.pk for pt in points if pt.delivery_method_id == d.pk
                ],
            }
            for d in methods
        ],
    }
