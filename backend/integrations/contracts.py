from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Mapping
from uuid import UUID


ENGINEERING_READ = "engineering:read"
ENGINEERING_WRITE = "engineering:write"
EXPORT_READ = "export:read"
ALL_SCOPES: tuple[str, ...] = (
    ENGINEERING_READ,
    ENGINEERING_WRITE,
    EXPORT_READ,
)


@dataclass(frozen=True, slots=True)
class ApiClientPrincipal:
    client_id: UUID
    name: str
    scopes: frozenset[str] = field(default_factory=frozenset)
    role: str = "INTEGRATION"
    is_authenticated: bool = True
    is_active: bool = True

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


@dataclass(frozen=True, slots=True)
class IssuedApiClient:
    client_id: UUID
    name: str
    key_prefix: str
    raw_api_key: str
    scopes: tuple[str, ...]
    is_active: bool


@dataclass(frozen=True, slots=True)
class EngineeringStatusCommand:
    order_id: UUID
    actor_client_id: UUID
    target_status: str | None = None
    reason: str = ""
    actual_material_name: str | None = None
    actual_material_g: Decimal | None = None
    actual_print_hours: Decimal | None = None
    printer_name: str | None = None
    notes: str | None = None


@dataclass(frozen=True, slots=True)
class EngineeringStatusReceipt:
    order_id: UUID
    order_number: str
    previous_status: str
    status: str
    actual_data: Mapping[str, object]
    event_id: UUID | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ExportQuery:
    status: str | None = None
    order_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None
    horizon_days: int = 7
