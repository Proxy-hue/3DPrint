from .contracts import ModelValidationOutcome
from .services import validate_stored_model


def validate_model_task(
    model_id: int,
    owner_id: int,
    technology: str | None = None,
    assembly_selected: bool = False,
) -> ModelValidationOutcome | None:
    return validate_stored_model(
        model_id=model_id,
        owner_id=owner_id,
        technology=technology,
        assembly_selected=assembly_selected,
    )
