"""Правила совместимости параметров заказа (спецификация 5.2.5).

Чистая функция без обращения к БД: удобно тестировать и вызывать
из модуля validation.
"""
from .dto import DELIVERY_PICKUP, CompatibilityIssue

MATERIAL_TECHNOLOGY = 'MATERIAL_TECHNOLOGY'
QUALITY_TECHNOLOGY = 'QUALITY_TECHNOLOGY'
COLOR_MATERIAL = 'COLOR_MATERIAL'
POST_TECHNOLOGY = 'POST_TECHNOLOGY'
POST_TRANSPARENT = 'POST_TRANSPARENT'
ASSEMBLY_3MF = 'ASSEMBLY_REQUIRES_MULTIBODY_3MF'
PICKUP_POINT = 'PICKUP_POINT_REQUIRED'


def check_compatibility(
    *,
    technology_id,
    material_technology_ids,
    material_color_ids,
    color_id,
    color_is_transparent,
    quality_technology_id,
    post_processings=(),
    delivery_type=None,
    pickup_point_active=None,
    model=None,
):
    """Возвращает список нарушений (пустой список — сочетание допустимо).

    * материал допустим для технологии;
    * профиль качества принадлежит технологии;
    * цвет входит в список цветов материала;
    * постобработка допустима для технологии и цвета;
    * «Сборка» — только для 3MF с несколькими телами (если модель уже
      разобрана; иначе правило не проверяется);
    * для самовывоза выбран активный пункт выдачи.
    """
    issues = []

    if technology_id not in material_technology_ids:
        issues.append(CompatibilityIssue(
            MATERIAL_TECHNOLOGY,
            'Материал недоступен для выбранной технологии.'
        ))
    if quality_technology_id != technology_id:
        issues.append(CompatibilityIssue(
            QUALITY_TECHNOLOGY,
            'Профиль качества не относится к выбранной технологии.'
        ))
    if color_id not in material_color_ids:
        issues.append(CompatibilityIssue(
            COLOR_MATERIAL,
            'Выбранный цвет недоступен для этого материала.'
        ))

    for rule in post_processings:
        if technology_id in rule.incompatible_technology_ids:
            issues.append(CompatibilityIssue(
                POST_TECHNOLOGY,
                f'Постобработка «{rule.code}» недоступна для технологии.'
            ))
        if rule.forbids_transparent and color_is_transparent:
            issues.append(CompatibilityIssue(
                POST_TRANSPARENT,
                f'Постобработка «{rule.code}» недоступна '
                f'для прозрачного материала.'
            ))
        if rule.requires_multibody_3mf and model is not None:
            known = model.format is not None and model.body_count is not None
            if known and (model.format.upper() != '3MF'
                          or model.body_count < 2):
                issues.append(CompatibilityIssue(
                    ASSEMBLY_3MF,
                    'Сборка доступна только для файла 3MF '
                    'с несколькими телами.'
                ))

    if delivery_type == DELIVERY_PICKUP and pickup_point_active is not True:
        issues.append(CompatibilityIssue(
            PICKUP_POINT,
            'Для самовывоза нужно выбрать активный пункт выдачи.'
        ))

    return issues
