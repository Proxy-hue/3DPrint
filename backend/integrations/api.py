from typing import Any, Protocol
from uuid import UUID

from .contracts import (
    EngineeringStatusCommand,
    EngineeringStatusReceipt,
    ExportQuery,
    IssuedApiClient,
)
from .models import ApiClient
from .services import (
    IntegrationNotFoundError,
    IntegrationServiceError,
    InvalidStatusTransitionError,
    export_events,
    export_load,
    export_orders,
    get_engineering_order_with_model,
    issue_api_client,
    list_engineering_orders,
    render_csv,
    revoke_api_client,
    rotate_api_client_key,
    update_engineering_order_status,
)


class IntegrationPublicAPI(Protocol):
    def issue_api_client(
        self,
        name: str,
        scopes: list[str] | tuple[str, ...],
        *,
        is_active: bool = True,
    ) -> IssuedApiClient: ...

    def rotate_api_client_key(self, client_id: UUID) -> IssuedApiClient: ...

    def revoke_api_client(self, client_id: UUID) -> ApiClient: ...

    def list_engineering_orders(
        self,
        *,
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]: ...

    def update_engineering_order_status(
        self,
        command: EngineeringStatusCommand,
    ) -> EngineeringStatusReceipt: ...

    def export_orders(self, query: ExportQuery) -> list[dict[str, Any]]: ...

    def export_events(self, query: ExportQuery) -> list[dict[str, Any]]: ...

    def export_load(self, query: ExportQuery) -> list[dict[str, Any]]: ...


__all__ = [
    "IntegrationNotFoundError",
    "IntegrationPublicAPI",
    "IntegrationServiceError",
    "InvalidStatusTransitionError",
    "export_events",
    "export_load",
    "export_orders",
    "get_engineering_order_with_model",
    "issue_api_client",
    "list_engineering_orders",
    "render_csv",
    "revoke_api_client",
    "rotate_api_client_key",
    "update_engineering_order_status",
]
