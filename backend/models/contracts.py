from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import BinaryIO, Mapping

from validation.api import ValidationContext, ValidationFinding


@dataclass(frozen=True, slots=True)
class ModelReceipt:
    model_id: int
    status: str


@dataclass(frozen=True, slots=True)
class ModelUploadCommand:
    owner_id: int
    draft_id: str
    filename: str
    file: BinaryIO
    validation_context: ValidationContext | None = None


@dataclass(frozen=True, slots=True)
class ModelUploadOutcome:
    draft_id: str
    model: ModelReceipt | None
    findings: tuple[ValidationFinding, ...]
    queue_error: str | None = None


@dataclass(frozen=True, slots=True)
class ModelValidationOutcome:
    valid: bool | None
    status: str
    dimensions_mm: tuple[float, float, float] | None
    errors: tuple[str, ...]
    queued: bool = True


@dataclass(frozen=True, slots=True)
class CreateOrderCommand:
    owner_id: int
    model_id: int
    configuration: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PriceAdjustmentCommand:
    order_id: int
    actor_id: int
    amount: Decimal
    reason: str


@dataclass(frozen=True, slots=True)
class PriceAdjustmentAudit:
    order_id: int
    actor_id: int
    previous_amount: Decimal
    new_amount: Decimal
    reason: str
    changed_at: datetime


@dataclass(frozen=True, slots=True)
class OrderSummary:
    order_id: int
    owner_id: int
    status: str
    price: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PriceAdjustmentReceipt:
    order: OrderSummary
    audit: PriceAdjustmentAudit
