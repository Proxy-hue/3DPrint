from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Principal:
    user_id: int
    role: str
    permissions: frozenset[str] = field(default_factory=frozenset)
    is_active: bool = True
    is_senior: bool = False
