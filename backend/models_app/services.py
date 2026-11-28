import logging
from uuid import UUID

from botocore.exceptions import BotoCoreError, ClientError

from validation.api import ValidationContext, ValidationFinding, validate_file

from .contracts import ModelValidationOutcome
from .models import ModelVersion, PrintModel, ValidationResultRecord


logger = logging.getLogger(__name__)


def _ensure_current_version(model: PrintModel) -> ModelVersion:
    current = model.versions.filter(is_current=True).first()
    if current is not None:
        return current
    return ModelVersion.objects.create(
        print_model=model,
        version=1,
        file=model.file.name,
        file_name=model.original_name,
        format=model.format,
        size_bytes=model.size,
        storage_key=model.file.name,
        is_current=True,
    )


def validate_stored_model(
    model_id: UUID,
    owner_id: UUID,
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

    current_version = _ensure_current_version(model)
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
        return _save_storage_error(
            model,
            current_version,
            "Исходный файл не найден в хранилище.",
        )
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code")
        if error_code not in {"NoSuchKey", "NotFound", "404"}:
            logger.exception("Could not read stored model %s", model_id)
            return _save_storage_error(
                model,
                current_version,
                "Хранилище временно недоступно; проверку можно повторить.",
                retryable=True,
            )
        return _save_storage_error(
            model,
            current_version,
            "Исходный файл не найден в хранилище.",
        )
    except (BotoCoreError, OSError):
        logger.exception("Could not read stored model %s", model_id)
        return _save_storage_error(
            model,
            current_version,
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
        "verdict": result.verdict,
        "findings": findings,
        "dimensions_mm": dimensions,
        "volume_cm3": result.volume_cm3,
        "needs_support": result.needs_support,
        "support_factor": result.support_factor,
    }
    if dimensions is None:
        model.width_mm = None
        model.height_mm = None
        model.depth_mm = None
    else:
        model.width_mm, model.height_mm, model.depth_mm = dimensions
    model.volume_cm3 = result.volume_cm3
    model.save(
        update_fields=(
            "status",
            "validation_errors",
            "validation_result",
            "width_mm",
            "height_mm",
            "depth_mm",
            "volume_cm3",
            "updated_at",
        )
    )

    current_version.bbox_x = model.width_mm
    current_version.bbox_y = model.height_mm
    current_version.bbox_z = model.depth_mm
    current_version.volume_cm3 = result.volume_cm3
    current_version.save(
        update_fields=("bbox_x", "bbox_y", "bbox_z", "volume_cm3", "updated_at")
    )
    ValidationResultRecord.objects.create(
        model_version=current_version,
        verdict=result.verdict,
        issues=findings,
        needs_support=result.needs_support,
    )

    return ModelValidationOutcome(
        valid=result.valid,
        status=model.status,
        dimensions_mm=result.dimensions_mm,
        errors=tuple(model.validation_errors),
        volume_cm3=result.volume_cm3,
        verdict=result.verdict,
    )


def _save_storage_error(
    model: PrintModel,
    current_version: ModelVersion,
    message: str,
    *,
    retryable: bool = False,
) -> ModelValidationOutcome:
    finding = ValidationFinding(
        code=None if retryable else "E-02",
        severity="error",
        message=message,
    )
    issues = [
        {
            "code": finding.code,
            "severity": finding.severity,
            "message": finding.message,
        }
    ]
    model.status = (
        PrintModel.Status.UPLOADED if retryable else PrintModel.Status.REJECTED
    )
    model.validation_errors = [message]
    model.validation_result = {
        "state": "storage_error",
        "valid": None if retryable else False,
        "verdict": None if retryable else "ERROR",
        "findings": issues,
        "dimensions_mm": None,
        "volume_cm3": None,
        "needs_support": False,
        "support_factor": 0.0,
    }
    model.width_mm = None
    model.height_mm = None
    model.depth_mm = None
    model.volume_cm3 = None
    model.save(
        update_fields=(
            "status",
            "validation_errors",
            "validation_result",
            "width_mm",
            "height_mm",
            "depth_mm",
            "volume_cm3",
            "updated_at",
        )
    )
    if not retryable:
        ValidationResultRecord.objects.create(
            model_version=current_version,
            verdict=ValidationResultRecord.Verdict.ERROR,
            issues=issues,
            needs_support=False,
        )
    return ModelValidationOutcome(
        valid=None if retryable else False,
        status=model.status,
        dimensions_mm=None,
        errors=(message,),
        verdict=None if retryable else "ERROR",
    )
