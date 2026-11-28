from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class ValidationContext:
    technology: str | None = None
    assembly_selected: bool = False
    material: str | None = None
    color: str | None = None
    quality_profile: str | None = None
    post_processing: tuple[str, ...] = ()
    printer_bounds_mm: tuple[tuple[float, float, float], ...] | None = None
    available_printers_count: int | None = None


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
    volume_cm3: float | None = None

    @property
    def verdict(self) -> Literal["OK", "WARNING", "ERROR"]:
        if not self.valid or any(f.severity == "error" for f in self.findings):
            return "ERROR"
        if any(f.severity == "warning" for f in self.findings):
            return "WARNING"
        return "OK"
