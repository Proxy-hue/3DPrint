import logging

from botocore.exceptions import BotoCoreError, ClientError

from validation.api import ValidationContext, ValidationFinding, validate_file

from .contracts import ModelValidationOutcome
from .models import PrintModel


logger = logging.getLogger(__name__)


def validate_stored_model(
    model_id: int,
    owner_id: int,
    technology: str | None = None,
    assembly_selected: bool = False,
) -> ModelValidationOutcome | None:
    model = PrintModel.objects.filter(pk=model_id, owner_id=owner_id).first()
    if model is None:
        logger.warning(
            "Skipping validation for missing model %s owned by %s",
            model_id,
            owner_id,
        )
        return None

    model.status = PrintModel.Status.VALIDATING
    model.save(update_fields=("status", "updated_at"))
    try:
        with model.file.open("rb") as model_file:
            context = (
                ValidationContext(
                    technology=technology,
                    assembly_selected=assembly_selected,
                )
                if technology is not None or assembly_selected
                else None
            )
            result = validate_file(
                model_file,
                model.original_name,
                context=context,
            )
    except FileNotFoundError:
        return _save_storage_error(model, "Исходный файл не найден в хранилище.")
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code not in {"NoSuchKey", "NotFound", "404"}:
            logger.exception("Could not read stored model %s", model_id)
            return _save_storage_error(
                model,
                "Хранилище временно недоступно; проверку можно повторить.",
                retryable=True,
            )
        return _save_storage_error(model, "Исходный файл не найден в хранилище.")
    except (BotoCoreError, OSError):
        logger.exception("Could not read stored model %s", model_id)
        return _save_storage_error(
            model,
            "Хранилище временно недоступно; проверку можно повторить.",
            retryable=True,
        )

    findings = [
        {
            "code": finding.code,
            "severity": finding.severity,
            "message": finding.message,
        }
        for finding in result.findings
    ]
    dimensions = (
        list(result.dimensions_mm)
        if result.dimensions_mm is not None
        else None
    )
    model.status = (
        PrintModel.Status.VALIDATED
        if result.valid
        else PrintModel.Status.REJECTED
    )
    model.validation_errors = [finding["message"] for finding in findings]
    model.validation_result = {
        "state": "completed",
        "valid": result.valid,
        "findings": findings,
        "dimensions_mm": dimensions,
        "needs_support": result.needs_support,
        "support_factor": result.support_factor,
    }
    if dimensions is None:
        model.width_mm = None
        model.height_mm = None
        model.depth_mm = None
    else:
        model.width_mm, model.height_mm, model.depth_mm = dimensions
    model.save(
        update_fields=(
            "status",
            "validation_errors",
            "validation_result",
            "width_mm",
            "height_mm",
            "depth_mm",
            "updated_at",
        )
    )
    return ModelValidationOutcome(
        valid=result.valid,
        status=model.status,
        dimensions_mm=result.dimensions_mm,
        errors=tuple(model.validation_errors),
    )


def _save_storage_error(
    model: PrintModel,
    message: str,
    *,
    retryable: bool = False,
) -> ModelValidationOutcome:
    finding = ValidationFinding(
        code=None if retryable else "E-02",
        severity="error",
        message=message,
    )
    model.status = (
        PrintModel.Status.UPLOADED if retryable else PrintModel.Status.REJECTED
    )
    model.validation_errors = [message]
    model.validation_result = {
        "state": "storage_error",
        "valid": None if retryable else False,
        "findings": [
            {
                "code": finding.code,
                "severity": finding.severity,
                "message": finding.message,
            }
        ],
        "dimensions_mm": None,
        "needs_support": False,
        "support_factor": 0.0,
    }
    model.width_mm = None
    model.height_mm = None
    model.depth_mm = None
    model.save(
        update_fields=(
            "status",
            "validation_errors",
            "validation_result",
            "width_mm",
            "height_mm",
            "depth_mm",
            "updated_at",
        )
    )
    return ModelValidationOutcome(
        valid=None if retryable else False,
        status=model.status,
        dimensions_mm=None,
        errors=(message,),
    )
