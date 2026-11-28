"""Тесты правил совместимости (без БД)."""
from catalog import rules
from catalog.dto import ModelInfo, PostProcessingRule

FDM, SLA, DMLS = 'fdm', 'sla', 'dmls'


def _check(**overrides):
    params = dict(
        technology_id=FDM,
        material_technology_ids={FDM},
        material_color_ids={'white', 'clear'},
        color_id='white',
        color_is_transparent=False,
        quality_technology_id=FDM,
        post_processings=[],
        delivery_type=None,
        pickup_point_active=None,
        model=None,
    )
    params.update(overrides)
    return [i.reason for i in rules.check_compatibility(**params)]


def test_valid_combination_has_no_issues():
    assert _check() == []


def test_material_not_for_technology():
    assert _check(material_technology_ids={SLA}) == [
        rules.MATERIAL_TECHNOLOGY
    ]


def test_quality_profile_of_other_technology():
    assert _check(quality_technology_id=SLA) == [rules.QUALITY_TECHNOLOGY]


def test_color_not_in_material_list():
    assert _check(color_id='red') == [rules.COLOR_MATERIAL]


def test_painting_unavailable_for_dmls():
    painting = PostProcessingRule(
        'PAINTING', incompatible_technology_ids=frozenset({DMLS}),
        forbids_transparent=True,
    )
    assert _check(
        technology_id=DMLS, material_technology_ids={DMLS},
        quality_technology_id=DMLS, post_processings=[painting],
    ) == [rules.POST_TECHNOLOGY]


def test_painting_unavailable_for_transparent_color():
    painting = PostProcessingRule('PAINTING', forbids_transparent=True)
    assert _check(
        color_id='clear', color_is_transparent=True,
        post_processings=[painting],
    ) == [rules.POST_TRANSPARENT]


def test_assembly_needs_multibody_3mf():
    assembly = PostProcessingRule('ASSEMBLY', requires_multibody_3mf=True)
    assert _check(
        post_processings=[assembly], model=ModelInfo('STL', 1)
    ) == [rules.ASSEMBLY_3MF]
    assert _check(
        post_processings=[assembly], model=ModelInfo('3MF', 1)
    ) == [rules.ASSEMBLY_3MF]
    assert _check(
        post_processings=[assembly], model=ModelInfo('3MF', 3)
    ) == []


def test_assembly_not_checked_until_model_is_analysed():
    assembly = PostProcessingRule('ASSEMBLY', requires_multibody_3mf=True)
    assert _check(post_processings=[assembly], model=ModelInfo()) == []
    assert _check(post_processings=[assembly], model=None) == []


def test_pickup_requires_active_point():
    assert _check(delivery_type='PICKUP') == [rules.PICKUP_POINT]
    assert _check(
        delivery_type='PICKUP', pickup_point_active=False
    ) == [rules.PICKUP_POINT]
    assert _check(delivery_type='PICKUP', pickup_point_active=True) == []
    assert _check(delivery_type='COURIER') == []
