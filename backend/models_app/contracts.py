from dataclasses import dataclass
from typing import BinaryIO
from uuid import UUID

from validation.api import ValidationContext, ValidationFinding


@dataclass(frozen=True, slots=True)
class ModelReceipt:
    model_id: UUID
    status: str
    version: int = 1


@dataclass(frozen=True, slots=True)
class ModelUploadCommand:
    owner_id: UUID
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
    volume_cm3: float | None = None
    verdict: str | None = None
