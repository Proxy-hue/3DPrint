"""Чистые (без Django) структуры данных модуля catalog.

Через них другие модули получают данные каталога (слой services,
спецификация 5.3.2), не обращаясь к моделям напрямую.
"""
from dataclasses import dataclass, field
from typing import Optional

SPEC_NONE = 'NONE'
SPEC_METAL = 'METAL'
SPEC_HIGH_STRENGTH_RESIN = 'HIGH_STRENGTH_RESIN'
SPEC_LARGE_FORMAT = 'LARGE_FORMAT'

PRINTER_ACTIVE = 'ACTIVE'
PRINTER_MAINTENANCE = 'MAINTENANCE'
PRINTER_RETIRED = 'RETIRED'

DELIVERY_PICKUP = 'PICKUP'
DELIVERY_COURIER = 'COURIER'

# Параметры расчёта и расписания по умолчанию (приложение 6 спецификации).
# Действующие значения хранятся в TariffVersion.params и заменяются
# заказчиком без изменения кода.
DEFAULT_TARIFF_PARAMS = {
    'min_cost': 300,                      # C_мин, ₽
    'printer_hours_per_day': 20,          # рабочих часов принтера в сутки
    'postprocessing_hours_per_day': 8,    # рабочих часов постобработки
    'load_horizon_days': 7,               # горизонт загрузки, сутки
    'changeover_penalty_hours': 2,        # K_пер, ч
    'specialized_penalty_hours': 24,      # K_спец, ч
}


def default_tariff_params():
    return dict(DEFAULT_TARIFF_PARAMS)


@dataclass(frozen=True)
class MaterialSpec:
    id: str
    technology_ids: frozenset
    color_ids: frozenset
    required_specialization: str = SPEC_NONE
    price_per_gram: float = 0.0
    density: float = 0.0


@dataclass(frozen=True)
class PrinterSpec:
    id: str
    name: str
    workshop_id: str
    workshop_name: str
    is_main_workshop: bool
    technology_id: str
    dims_mm: tuple
    specialization: str
    status: str
    material_ids: frozenset = field(default_factory=frozenset)


@dataclass(frozen=True)
class PostProcessingRule:
    code: str
    incompatible_technology_ids: frozenset = field(
        default_factory=frozenset
    )
    forbids_transparent: bool = False
    requires_multibody_3mf: bool = False


@dataclass(frozen=True)
class CompatibilityIssue:
    """Нарушение правил совместимости (код E-05 из таблицы 18)."""
    reason: str
    message: str
    code: str = 'E-05'


@dataclass(frozen=True)
class ModelInfo:
    """Сведения о загруженной модели, нужные для проверки опций."""
    format: Optional[str] = None
    body_count: Optional[int] = None
