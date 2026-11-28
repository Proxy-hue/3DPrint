from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ValidationContext:
    technology: str | None = None
    assembly_selected: bool = False


@dataclass(frozen=True, slots=True)
class ValidationFinding:
    code: str | None
    severity: Literal["error", "warning"]
    message: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    findings: tuple[ValidationFinding, ...]
    dimensions_mm: tuple[float, float, float] | None
    needs_support: bool = False
    support_factor: float = 0.0
