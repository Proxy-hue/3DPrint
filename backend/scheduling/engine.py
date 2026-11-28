"""Алгоритм распределения заказов (спецификация 5.2.5, OOS-16).

Чистый Python без обращения к БД: жёсткий фильтр, оценка (Score),
рекомендация и расчёт загрузки. ORM-обвязка — в ``services.py``.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from catalog.dto import (
    PRINTER_ACTIVE, SPEC_LARGE_FORMAT, SPEC_NONE, MaterialSpec, PrinterSpec,
)

# Коды причин исключения принтера жёстким фильтром
NOT_ACTIVE = 'NOT_ACTIVE'
TECHNOLOGY = 'TECHNOLOGY'
MATERIAL = 'MATERIAL'
COLOR = 'COLOR'
SIZE = 'SIZE'
SPECIALIZATION = 'SPECIALIZATION'
WORKSHOP = 'WORKSHOP'

NO_PRINTER_CODE = 'E-06'


@dataclass(frozen=True)
class OrderRequirements:
    """Что нужно заказу от оборудования (color_id=None — цвет не задан)."""
    technology_id: str
    material: MaterialSpec
    color_id: Optional[str]
    dims_mm: tuple
    print_hours: float


@dataclass(frozen=True)
class PrinterQueue:
    """Плановая очередь принтера."""
    queue_hours: float = 0.0
    last_material_id: Optional[str] = None


@dataclass(frozen=True)
class Recommendation:
    printer: PrinterSpec
    score: float
    queue_hours: float
    planned_start: object
    planned_end: object


@dataclass
class RecommendationResult:
    required_specialization: str
    candidates: list = field(default_factory=list)   # все подходящие
    recommendations: list = field(default_factory=list)  # топ-N
    excluded: dict = field(default_factory=dict)  # printer_id -> [причины]
    error_code: Optional[str] = None


def fits(dims, zone):
    """Упорядоченные габариты модели не больше упорядоченных габаритов зоны."""
    return all(d <= z for d, z in zip(sorted(dims), sorted(zone)))


def required_specialization(req, printers):
    """Специализация принтера, которой требует заказ.

    Материал может требовать специализацию (металл, высокопрочные смолы).
    Иначе «крупногабаритный» нужен, если модель не помещается ни на один
    активный принтер без специализации.
    """
    if req.material.required_specialization != SPEC_NONE:
        return req.material.required_specialization
    plain_fits = any(
        p.status == PRINTER_ACTIVE
        and p.specialization == SPEC_NONE
        and p.technology_id == req.technology_id
        and req.material.id in p.material_ids
        and fits(req.dims_mm, p.dims_mm)
        for p in printers
    )
    return SPEC_NONE if plain_fits else SPEC_LARGE_FORMAT


def evaluate_printer(printer, req, required):
    """Жёсткий фильтр: список причин, по которым принтер не подходит."""
    reasons = []
    if printer.status != PRINTER_ACTIVE:
        reasons.append(NOT_ACTIVE)
    if printer.technology_id != req.technology_id:
        reasons.append(TECHNOLOGY)
    if req.material.id not in printer.material_ids:
        reasons.append(MATERIAL)
    if req.color_id is not None and req.color_id not in req.material.color_ids:
        reasons.append(COLOR)
    if not fits(req.dims_mm, printer.dims_mm):
        reasons.append(SIZE)
    if required != SPEC_NONE:
        if printer.specialization != required:
            reasons.append(SPECIALIZATION)
        elif not printer.is_main_workshop:
            # S-DOM-02/03: специализированное оборудование — только
            # в основном цеху.
            reasons.append(WORKSHOP)
    return reasons


def is_reserve(printer, required):
    """Принтер специализирован, а заказ специализации не требует."""
    return printer.specialization != SPEC_NONE and required == SPEC_NONE


def score(printer, req, required, queue, params):
    """Score = T_своб + t + K_пер·[смена материала] + K_спец·[резерв]."""
    changeover = (
        queue.last_material_id is not None
        and queue.last_material_id != req.material.id
    )
    return (
        queue.queue_hours
        + req.print_hours
        + params['changeover_penalty_hours'] * (1 if changeover else 0)
        + params['specialized_penalty_hours']
        * (1 if is_reserve(printer, required) else 0)
    )


def working_hours_to_timedelta(hours, params):
    """Рабочие часы принтера -> календарное время (20 ч работы в сутки)."""
    return timedelta(hours=hours * 24.0 / params['printer_hours_per_day'])


def recommend(req, printers, queues, now, params, limit=3):
    """Подбор принтеров для заказа.

    ``printers`` — все принтеры (статус учитывается фильтром),
    ``queues`` — {printer_id: PrinterQueue}.
    """
    required = required_specialization(req, printers)
    result = RecommendationResult(required_specialization=required)
    scored = []
    for printer in printers:
        reasons = evaluate_printer(printer, req, required)
        if reasons:
            result.excluded[printer.id] = reasons
            continue
        queue = queues.get(printer.id, PrinterQueue())
        start = now + working_hours_to_timedelta(queue.queue_hours, params)
        end = start + working_hours_to_timedelta(req.print_hours, params)
        scored.append(Recommendation(
            printer=printer,
            score=score(printer, req, required, queue, params),
            queue_hours=queue.queue_hours,
            planned_start=start,
            planned_end=end,
        ))
    scored.sort(key=lambda r: (r.score, r.printer.name))
    result.candidates = scored
    result.recommendations = scored[:limit]
    if not scored:
        result.error_code = NO_PRINTER_CODE
    return result


# --- Загрузка оборудования ---

@dataclass(frozen=True)
class PlannedJob:
    printer_id: str
    start: object
    end: object
    hours: float


@dataclass(frozen=True)
class PrinterLoad:
    printer_id: str
    printer_name: str
    workshop_id: str
    workshop_name: str
    planned_hours: float
    load_percent: float
    idle_hours: float


@dataclass(frozen=True)
class WorkshopLoad:
    workshop_id: str
    workshop_name: str
    load_percent: float


def _hours_in_horizon(job, now, horizon_end):
    """Часть плановых часов задания, попадающая в горизонт."""
    duration = (job.end - job.start).total_seconds()
    if duration <= 0:
        return job.hours if now <= job.start <= horizon_end else 0.0
    overlap = (min(job.end, horizon_end)
               - max(job.start, now)).total_seconds()
    if overlap <= 0:
        return 0.0
    return job.hours * overlap / duration


def compute_load(printers, jobs, now, params):
    """Плановая загрузка и простои за горизонт (по умолчанию 7 суток).

    Загрузка принтера = плановые часы / (часов в сутки · дней горизонта).
    Загрузка цеха — среднее по его активным принтерам.
    """
    days = params['load_horizon_days']
    capacity = float(params['printer_hours_per_day'] * days)
    horizon_end = now + timedelta(days=days)
    planned = {}
    for job in jobs:
        planned[job.printer_id] = (
            planned.get(job.printer_id, 0.0)
            + _hours_in_horizon(job, now, horizon_end)
        )

    printer_loads = []
    by_workshop = {}
    for printer in printers:
        if printer.status != PRINTER_ACTIVE:
            continue
        hours = planned.get(printer.id, 0.0)
        percent = round(100.0 * hours / capacity, 1)
        printer_loads.append(PrinterLoad(
            printer_id=printer.id,
            printer_name=printer.name,
            workshop_id=printer.workshop_id,
            workshop_name=printer.workshop_name,
            planned_hours=round(hours, 2),
            load_percent=percent,
            idle_hours=round(max(0.0, capacity - hours), 2),
        ))
        by_workshop.setdefault(
            (printer.workshop_id, printer.workshop_name), []
        ).append(percent)

    workshop_loads = [
        WorkshopLoad(
            workshop_id=wid, workshop_name=wname,
            load_percent=round(sum(values) / len(values), 1),
        )
        for (wid, wname), values in sorted(
            by_workshop.items(), key=lambda item: item[0][1]
        )
    ]
    return printer_loads, workshop_loads, capacity
