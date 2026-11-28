"""Тесты алгоритма распределения на данных приложения 6 (без БД)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from catalog.dto import (
    MaterialSpec, PrinterSpec, default_tariff_params,
    SPEC_HIGH_STRENGTH_RESIN, SPEC_LARGE_FORMAT, SPEC_METAL, SPEC_NONE,
)
from scheduling import engine
from scheduling.engine import (
    OrderRequirements, PlannedJob, PrinterQueue,
)

FIXTURE = (Path(__file__).resolve().parent.parent
           / 'catalog' / 'fixtures' / 'initial_catalog.json')
NOW = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
PARAMS = default_tariff_params()


def _load():
    items = json.loads(FIXTURE.read_text(encoding='utf-8'))
    by_model = {}
    for item in items:
        by_model.setdefault(item['model'], {})[item['pk']] = item['fields']
    return by_model


DATA = _load()


def _pk(model, name_field, value):
    for pk, fields in DATA[f'catalog.{model}'].items():
        if fields[name_field] == value:
            return pk
    raise KeyError(value)


def tech(code):
    return _pk('technology', 'code', code)


def color(name):
    return _pk('color', 'name', name)


def material_spec(name):
    pk = _pk('material', 'name', name)
    f = DATA['catalog.material'][pk]
    return MaterialSpec(
        id=pk, technology_ids=frozenset(f['technologies']),
        color_ids=frozenset(f['colors']),
        required_specialization=f['required_specialization'],
        price_per_gram=float(f['price_per_gram']), density=f['density'],
    )


def printers(**status):
    result = []
    for pk, f in DATA['catalog.printer'].items():
        ws = DATA['catalog.workshop'][f['workshop']]
        result.append(PrinterSpec(
            id=pk, name=f['name'], workshop_id=f['workshop'],
            workshop_name=ws['name'], is_main_workshop=ws['is_main'],
            technology_id=f['technology'],
            dims_mm=(f['max_x'], f['max_y'], f['max_z']),
            specialization=f['specialization'],
            status=status.get(f['name'], f['status']),
            material_ids=frozenset(f['materials']),
        ))
    return result


def pid(name):
    return _pk('printer', 'name', name)


def req(technology, material, color_name, dims, hours=5.0):
    mat = material_spec(material)
    return OrderRequirements(
        technology_id=tech(technology), material=mat,
        color_id=color(color_name), dims_mm=dims, print_hours=hours,
    )


def run(request, queues=None, **status):
    return engine.recommend(
        request, printers(**status), queues or {}, NOW, PARAMS, limit=3
    )


def names(result):
    by_id = {p.id: p.name for p in printers()}
    return [by_id[c.printer.id] for c in result.candidates]


def test_small_fdm_order_prefers_plain_printers_over_large_format():
    result = run(req('FDM', 'PLA', 'белый', (30, 30, 30)))
    assert result.required_specialization == SPEC_NONE
    assert names(result) == ['FDM-01', 'FDM-02', 'FDM-XL']
    assert result.candidates[2].score == 5.0 + 24
    assert result.recommendations[0].printer.id == pid('FDM-01')


def test_large_model_requires_large_format_printer():
    result = run(req('FDM', 'PLA', 'белый', (400, 300, 60)))
    assert result.required_specialization == SPEC_LARGE_FORMAT
    assert names(result) == ['FDM-XL']
    assert 'SIZE' in result.excluded[pid('FDM-01')]
    assert 'SPECIALIZATION' in result.excluded[pid('FDM-02')]


def test_high_strength_resin_only_on_specialized_printer():
    result = run(req('SLA', 'Высокопрочная смола', 'серый', (40, 40, 40)))
    assert result.required_specialization == SPEC_HIGH_STRENGTH_RESIN
    assert names(result) == ['SLA-HS']
    assert 'MATERIAL' in result.excluded[pid('SLA-01')]


def test_standard_resin_prefers_plain_sla_over_specialized():
    result = run(req('SLA', 'Стандартная смола', 'серый', (40, 40, 40)))
    assert names(result) == ['SLA-01', 'SLA-HS']
    assert result.candidates[1].score == 5.0 + 24


def test_metal_goes_to_dmls_in_main_workshop():
    result = run(req('DMLS', 'Нержавеющая сталь 316L', 'металлик',
                     (30, 30, 30)))
    assert result.required_specialization == SPEC_METAL
    assert names(result) == ['DMLS-01']


def test_retired_dmls_printer_gives_e06():
    result = run(req('DMLS', 'Нержавеющая сталь 316L', 'металлик',
                     (30, 30, 30)), **{'DMLS-01': 'RETIRED'})
    assert result.error_code == 'E-06'
    assert result.candidates == []
    assert 'NOT_ACTIVE' in result.excluded[pid('DMLS-01')]


def test_oversized_model_gives_e06():
    result = run(req('FDM', 'PLA', 'белый', (700, 700, 700)))
    assert result.error_code == 'E-06'


def test_color_unavailable_for_material_excludes_everything():
    result = run(req('FDM', 'ABS', 'красный', (30, 30, 30)))
    assert result.error_code == 'E-06'
    assert all('COLOR' in r for r in result.excluded.values()
               if 'TECHNOLOGY' not in r)


def test_queue_hours_shift_choice_and_planned_dates():
    queues = {pid('FDM-01'): PrinterQueue(queue_hours=10.0)}
    result = run(req('FDM', 'PLA', 'белый', (30, 30, 30)), queues)
    best = result.recommendations[0]
    assert best.printer.id == pid('FDM-02')
    assert best.planned_start == NOW
    assert best.planned_end == NOW + timedelta(hours=6)
    first = [c for c in result.candidates if c.printer.id == pid('FDM-01')]
    assert first[0].planned_start == NOW + timedelta(hours=12)


def test_material_changeover_penalty():
    abs_id = material_spec('ABS').id
    queues = {pid('FDM-01'): PrinterQueue(0.0, last_material_id=abs_id)}
    result = run(req('FDM', 'PLA', 'белый', (30, 30, 30)), queues)
    assert names(result)[0] == 'FDM-02'
    penalised = [c for c in result.candidates
                 if c.printer.id == pid('FDM-01')][0]
    assert penalised.score == 5.0 + 2


def test_specialized_printer_outside_main_workshop_is_excluded():
    request = req('DMLS', 'Нержавеющая сталь 316L', 'металлик', (30, 30, 30))
    moved = [
        PrinterSpec(**{**p.__dict__, 'is_main_workshop': False})
        if p.name == 'DMLS-01' else p for p in printers()
    ]
    result = engine.recommend(request, moved, {}, NOW, PARAMS)
    assert result.error_code == 'E-06'
    assert 'WORKSHOP' in result.excluded[pid('DMLS-01')]


def test_load_is_prorated_over_horizon():
    capacity = 20 * 7
    jobs = [
        PlannedJob(pid('FDM-01'), NOW, NOW + timedelta(hours=14), 14.0),
        PlannedJob(pid('FDM-02'), NOW + timedelta(days=6, hours=12),
                   NOW + timedelta(days=7, hours=12), 20.0),
    ]
    loads, workshops, cap = engine.compute_load(
        printers(**{'DMLS-01': 'MAINTENANCE'}), jobs, NOW, PARAMS
    )
    assert cap == capacity
    by_name = {item.printer_name: item for item in loads}
    assert by_name['FDM-01'].planned_hours == 14.0
    assert by_name['FDM-01'].load_percent == 10.0
    assert by_name['FDM-01'].idle_hours == 126.0
    assert by_name['FDM-02'].planned_hours == 10.0
    assert 'DMLS-01' not in by_name
    main = [w for w in workshops if w.workshop_name == 'Основной цех'][0]
    assert main.load_percent == round(10.0 / 3, 1)


def test_order_without_color_skips_color_check():
    request = OrderRequirements(
        technology_id=tech('FDM'), material=material_spec('PLA'),
        color_id=None, dims_mm=(30, 30, 30), print_hours=5.0,
    )
    result = run(request)
    assert names(result) == ['FDM-01', 'FDM-02', 'FDM-XL']


def test_reserve_flag_matches_penalty():
    request = req('FDM', 'PLA', 'белый', (30, 30, 30))
    result = run(request)
    reserve = {c.printer.name: engine.is_reserve(c.printer, SPEC_NONE)
               for c in result.candidates}
    assert reserve == {'FDM-01': False, 'FDM-02': False, 'FDM-XL': True}
