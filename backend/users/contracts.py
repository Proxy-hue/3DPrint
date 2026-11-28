from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: UUID
    role: str
    permissions: frozenset[str] = field(default_factory=frozenset)
    is_active: bool = True
    is_senior: bool = False
