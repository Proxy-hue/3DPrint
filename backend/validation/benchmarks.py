import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TechnologyTariff:
    code: str
    fill_factor: float
    support_factor: float
    hourly_rate: float
    setup_cost: float


@dataclass(frozen=True, slots=True)
class QualityTariff:
    flow_cm3_h: float
    price_factor: float


@dataclass(frozen=True, slots=True)
class MaterialTariff:
    density_g_cm3: float
    price_per_gram: float


TECHNOLOGIES: dict[str, TechnologyTariff] = {
    "FDM": TechnologyTariff("FDM", fill_factor=0.35, support_factor=0.15, hourly_rate=120.0, setup_cost=150.0),
    "SLA": TechnologyTariff("SLA", fill_factor=0.60, support_factor=0.20, hourly_rate=200.0, setup_cost=250.0),
    "DMLS": TechnologyTariff("DMLS", fill_factor=1.00, support_factor=0.10, hourly_rate=2500.0, setup_cost=3000.0),
}

QUALITY_PROFILES: dict[tuple[str, str], QualityTariff] = {
    ("FDM", "Черновое"): QualityTariff(flow_cm3_h=25.0, price_factor=0.90),
    ("FDM", "Стандартное"): QualityTariff(flow_cm3_h=15.0, price_factor=1.00),
    ("FDM", "Высокое"): QualityTariff(flow_cm3_h=7.0, price_factor=1.20),
    ("SLA", "Стандартное"): QualityTariff(flow_cm3_h=20.0, price_factor=1.00),
    ("SLA", "Высокое"): QualityTariff(flow_cm3_h=10.0, price_factor=1.25),
    ("DMLS", "Стандартное"): QualityTariff(flow_cm3_h=5.0, price_factor=1.00),
}

MATERIALS: dict[str, MaterialTariff] = {
    "PLA": MaterialTariff(density_g_cm3=1.24, price_per_gram=3.0),
    "ABS": MaterialTariff(density_g_cm3=1.04, price_per_gram=3.5),
    "Нейлон (PA12)": MaterialTariff(density_g_cm3=1.01, price_per_gram=6.0),
    "Стандартная смола": MaterialTariff(density_g_cm3=1.10, price_per_gram=8.0),
    "Высокопрочная смола": MaterialTariff(density_g_cm3=1.15, price_per_gram=15.0),
    "Нержавеющая сталь 316L": MaterialTariff(density_g_cm3=7.90, price_per_gram=40.0),
}

POST_PROCESSING: dict[str, tuple[float, float]] = {
    "Шлифовка": (400.0, 2.0),
    "Покраска": (800.0, 6.0),
    "Сборка": (600.0, 3.0),
}

DELIVERY_METHODS: dict[str, tuple[float, int]] = {
    "самовывоз": (0.0, 0),
    "курьер": (350.0, 2),
}

MIN_MANUFACTURING_COST = 300.0
PRINTER_HOURS_PER_DAY = 20.0
POST_PROCESSING_HOURS_PER_DAY = 8.0


def calculate_spec_quote(
    *,
    technology: str,
    material: str,
    quality: str,
    volume_cm3: float,
    quantity: int,
    needs_support: bool = False,
    post_processing: tuple[str, ...] = (),
    delivery: str = "самовывоз",
    queue_wait_hours: float = 0.0,
    adjustment: float = 0.0,
) -> tuple[int, int]:
    tech = TECHNOLOGIES[technology]
    qual = QUALITY_PROFILES[(technology, quality)]
    mat = MATERIALS[material]
    s = 1.0 if needs_support else 0.0

    effective_volume = quantity * volume_cm3 * tech.fill_factor * (1.0 + tech.support_factor * s)
    mass_g = effective_volume * mat.density_g_cm3
    print_hours = effective_volume / qual.flow_cm3_h
    cost_material = mass_g * mat.price_per_gram
    cost_machine = print_hours * tech.hourly_rate
    cost_base = (cost_material + cost_machine + tech.setup_cost) * qual.price_factor

    post_cost_per_item = sum(POST_PROCESSING[item][0] for item in post_processing)
    post_hours_per_item = sum(POST_PROCESSING[item][1] for item in post_processing)
    cost_post = quantity * post_cost_per_item

    delivery_cost, delivery_days = DELIVERY_METHODS[delivery]
    total_rub = round(
        max(MIN_MANUFACTURING_COST, cost_base + cost_post) + delivery_cost + adjustment
    )
    print_days = math.ceil((queue_wait_hours + print_hours) / PRINTER_HOURS_PER_DAY)
    post_days = math.ceil((quantity * post_hours_per_item) / POST_PROCESSING_HOURS_PER_DAY) if post_processing else 0
    total_days = print_days + post_days + delivery_days
    return total_rub, total_days


TYPICAL_BENCHMARK_CASES: tuple[dict, ...] = (
    {"id": "T-01", "tech": "FDM", "mat": "PLA", "qual": "Стандартное", "vol": 18.0, "qty": 1, "post": (), "deliv": "самовывоз", "support": False, "price": 300, "days": 1},
    {"id": "T-02", "tech": "FDM", "mat": "ABS", "qual": "Стандартное", "vol": 55.0, "qty": 2, "post": ("Шлифовка",), "deliv": "курьер", "support": False, "price": 1748, "days": 4},
    {"id": "T-03", "tech": "FDM", "mat": "Нейлон (PA12)", "qual": "Высокое", "vol": 14.0, "qty": 4, "post": (), "deliv": "самовывоз", "support": False, "price": 726, "days": 1},
    {"id": "T-04", "tech": "FDM", "mat": "PLA", "qual": "Черновое", "vol": 60.0, "qty": 1, "post": (), "deliv": "самовывоз", "support": True, "price": 320, "days": 1},
    {"id": "T-05", "tech": "FDM", "mat": "PLA", "qual": "Стандартное", "vol": 40.0, "qty": 3, "post": ("Покраска",), "deliv": "курьер", "support": False, "price": 3392, "days": 6},
    {"id": "T-06", "tech": "FDM", "mat": "ABS", "qual": "Стандартное", "vol": 9.0, "qty": 10, "post": (), "deliv": "самовывоз", "support": False, "price": 517, "days": 1},
    {"id": "T-07", "tech": "FDM", "mat": "PLA", "qual": "Высокое", "vol": 85.0, "qty": 1, "post": ("Шлифовка", "Покраска"), "deliv": "курьер", "support": False, "price": 2475, "days": 4},
    {"id": "T-08", "tech": "FDM", "mat": "PLA", "qual": "Черновое", "vol": 210.0, "qty": 1, "post": (), "deliv": "самовывоз", "support": True, "price": 783, "days": 1},
    {"id": "T-09", "tech": "FDM", "mat": "ABS", "qual": "Стандартное", "vol": 48.0, "qty": 2, "post": ("Шлифовка",), "deliv": "самовывоз", "support": False, "price": 1341, "days": 2},
    {"id": "T-10", "tech": "FDM", "mat": "PLA", "qual": "Стандартное", "vol": 12.0, "qty": 6, "post": (), "deliv": "курьер", "support": False, "price": 795, "days": 3},
    {"id": "T-11", "tech": "FDM", "mat": "PLA", "qual": "Стандартное", "vol": 70.0, "qty": 1, "post": ("Сборка",), "deliv": "самовывоз", "support": False, "price": 1037, "days": 2},
    {"id": "T-12", "tech": "FDM", "mat": "ABS", "qual": "Стандартное", "vol": 150.0, "qty": 1, "post": ("Шлифовка", "Покраска"), "deliv": "курьер", "support": True, "price": 2403, "days": 4},
    {"id": "T-13", "tech": "FDM", "mat": "PLA", "qual": "Стандартное", "vol": 320.0, "qty": 1, "post": (), "deliv": "самовывоз", "support": False, "price": 1463, "days": 1},
    {"id": "T-14", "tech": "FDM", "mat": "ABS", "qual": "Черновое", "vol": 380.0, "qty": 1, "post": ("Шлифовка",), "deliv": "самовывоз", "support": True, "price": 1697, "days": 2},
    {"id": "T-15", "tech": "SLA", "mat": "Стандартная смола", "qual": "Высокое", "vol": 12.0, "qty": 3, "post": ("Покраска",), "deliv": "самовывоз", "support": False, "price": 3490, "days": 4},
    {"id": "T-16", "tech": "SLA", "mat": "Стандартная смола", "qual": "Высокое", "vol": 2.0, "qty": 5, "post": (), "deliv": "курьер", "support": False, "price": 879, "days": 3},
    {"id": "T-17", "tech": "SLA", "mat": "Стандартная смола", "qual": "Стандартное", "vol": 15.0, "qty": 2, "post": (), "deliv": "самовывоз", "support": False, "price": 588, "days": 1},
    {"id": "T-18", "tech": "SLA", "mat": "Стандартная смола", "qual": "Стандартное", "vol": 50.0, "qty": 1, "post": ("Шлифовка",), "deliv": "курьер", "support": False, "price": 1564, "days": 4},
    {"id": "T-19", "tech": "SLA", "mat": "Высокопрочная смола", "qual": "Стандартное", "vol": 30.0, "qty": 2, "post": (), "deliv": "самовывоз", "support": False, "price": 1231, "days": 1},
    {"id": "T-20", "tech": "SLA", "mat": "Высокопрочная смола", "qual": "Высокое", "vol": 25.0, "qty": 4, "post": (), "deliv": "курьер", "support": False, "price": 3456, "days": 3},
    {"id": "T-21", "tech": "DMLS", "mat": "Нержавеющая сталь 316L", "qual": "Стандартное", "vol": 10.0, "qty": 2, "post": (), "deliv": "самовывоз", "support": False, "price": 19320, "days": 1},
    {"id": "T-22", "tech": "DMLS", "mat": "Нержавеющая сталь 316L", "qual": "Стандартное", "vol": 20.0, "qty": 1, "post": ("Шлифовка",), "deliv": "курьер", "support": False, "price": 20070, "days": 4},
    {"id": "T-23", "tech": "DMLS", "mat": "Нержавеющая сталь 316L", "qual": "Стандартное", "vol": 22.0, "qty": 1, "post": (), "deliv": "самовывоз", "support": True, "price": 22747, "days": 1},
    {"id": "T-24", "tech": "DMLS", "mat": "Нержавеющая сталь 316L", "qual": "Стандартное", "vol": 30.0, "qty": 2, "post": ("Шлифовка",), "deliv": "самовывоз", "support": False, "price": 52760, "days": 2},
)
