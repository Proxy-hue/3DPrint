import logging
import os
from pathlib import PurePosixPath
from typing import Protocol
from uuid import UUID

import django_rq
from botocore.exceptions import BotoCoreError
from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import Max
from redis.exceptions import RedisError

from validation.api import SUPPORTED_FORMATS, ValidationFinding

from .contracts import (
    ModelReceipt,
    ModelUploadCommand,
    ModelUploadOutcome,
    ModelValidationOutcome,
)
from .models import ModelVersion, PrintModel
from .tasks import validate_model_task


logger = logging.getLogger(__name__)
MAX_MODEL_FILE_SIZE = 50 * 1024 * 1024
QUEUE_UNAVAILABLE_MESSAGE = (
    "Файл сохранён, но фоновая проверка не запущена. "
    "Повторите проверку позже."
)


class ModelsPublicAPI(Protocol):
    def upload_model(self, command: ModelUploadCommand) -> ModelUploadOutcome: ...

    def upload_model_version(
        self,
        model_id: UUID,
        command: ModelUploadCommand,
        *,
        order_id: UUID | None = None,
    ) -> ModelUploadOutcome | None: ...

    def revalidate_model(
        self,
        model_id: UUID,
        *,
        owner_id: UUID,
        technology: str | None = None,
        assembly_selected: bool = False,
    ) -> ModelValidationOutcome | None: ...


def _finding(code: str, message: str) -> ValidationFinding:
    return ValidationFinding(code=code, severity="error", message=message)


def _file_size(file) -> int:
    reported_size = getattr(file, "size", None)
    if isinstance(reported_size, int):
        return reported_size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    return size


def _safe_original_name(filename: str) -> str:
    name = PurePosixPath(filename.replace("\\", "/")).name.strip()
    return (name or "model")[:255]


def _validate_upload_basics(command: ModelUploadCommand) -> tuple[str, int, str] | ModelUploadOutcome:
    extension = os.path.splitext(command.filename)[1].lower()
    if extension not in SUPPORTED_FORMATS:
        return ModelUploadOutcome(
            draft_id=command.draft_id,
            model=None,
            findings=(_finding("E-01", "Поддерживаются только файлы STL, OBJ и 3MF."),),
        )

    try:
        size = _file_size(command.file)
        command.file.seek(0)
    except (AttributeError, OSError, TypeError, ValueError):
        return ModelUploadOutcome(
            draft_id=command.draft_id,
            model=None,
            findings=(_finding("E-02", "Не удалось прочитать загруженный файл."),),
        )
    if size > MAX_MODEL_FILE_SIZE:
        return ModelUploadOutcome(
            draft_id=command.draft_id,
            model=None,
            findings=(_finding("E-01", "Размер файла превышает 50 МиБ."),),
        )
    if size == 0:
        return ModelUploadOutcome(
            draft_id=command.draft_id,
            model=None,
            findings=(_finding("E-02", "Файл пуст."),),
        )

    return extension, size, _safe_original_name(command.filename)


def _mark_queue_failure(model_id: UUID, owner_id: UUID) -> None:
    model = PrintModel.objects.filter(pk=model_id, owner_id=owner_id).first()
    if model is None:
        return
    model.status = PrintModel.Status.UPLOADED
    model.validation_errors = [QUEUE_UNAVAILABLE_MESSAGE]
    model.validation_result = {
        "state": "queue_error",
        "valid": None,
        "findings": [],
        "error": QUEUE_UNAVAILABLE_MESSAGE,
    }
    model.save(
        update_fields=("status", "validation_errors", "validation_result", "updated_at")
    )


def _enqueue_validation(
    model_id: UUID,
    owner_id: UUID,
    technology: str | None,
    assembly_selected: bool,
) -> None:
    try:
        django_rq.get_queue("default").enqueue(
            validate_model_task,
            model_id,
            owner_id,
            technology,
            assembly_selected,
        )
    except (OSError, RedisError):
        if settings.DEBUG and getattr(settings, "SYNC_VALIDATION_FALLBACK", False):
            logger.warning(
                "Redis unavailable; running synchronous validation fallback for model %s",
                model_id,
            )
            validate_model_task(model_id, owner_id, technology, assembly_selected)
            return
        logger.exception("Could not enqueue validation for model %s", model_id)
        _mark_queue_failure(model_id, owner_id)


def _schedule_validation(
    model: PrintModel,
    *,
    technology: str | None = None,
    assembly_selected: bool = False,
) -> None:
    model.status = PrintModel.Status.VALIDATING
    model.validation_errors = []
    model.validation_result = {
        "state": "queued",
        "valid": None,
        "findings": [],
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
    transaction.on_commit(
        lambda: _enqueue_validation(
            model.pk,
            model.owner_id,
            technology,
            assembly_selected,
        )
    )


def upload_model(command: ModelUploadCommand) -> ModelUploadOutcome:
    basics = _validate_upload_basics(command)
    if isinstance(basics, ModelUploadOutcome):
        return basics
    extension, size, original_name = basics

    model = PrintModel(
        owner_id=command.owner_id,
        draft_id=command.draft_id,
        original_name=original_name,
        format=SUPPORTED_FORMATS[extension],
        size=size,
    )
    try:
        model.file.save(original_name, command.file, save=False)
    except (BotoCoreError, OSError, ValueError):
        logger.exception("Could not store uploaded model for owner %s", command.owner_id)
        return ModelUploadOutcome(
            draft_id=command.draft_id,
            model=None,
            findings=(_finding("E-02", "Не удалось сохранить файл в хранилище."),),
        )

    try:
        with transaction.atomic():
            model.save()
            ModelVersion.objects.create(
                print_model=model,
                version=1,
                file=model.file.name,
                file_name=model.original_name,
                format=model.format,
                size_bytes=model.size,
                storage_key=model.file.name,
                is_current=True,
            )
            _schedule_validation(
                model,
                technology=(
                    command.validation_context.technology
                    if command.validation_context
                    else None
                ),
                assembly_selected=(
                    command.validation_context.assembly_selected
                    if command.validation_context
                    else False
                ),
            )
    except DatabaseError:
        model.file.delete(save=False)
        raise

    model.refresh_from_db()
    queue_error = (
        model.validation_result.get("error")
        if model.validation_result.get("state") == "queue_error"
        else None
    )
    return ModelUploadOutcome(
        draft_id=command.draft_id,
        model=ModelReceipt(model_id=model.pk, status=model.status, version=1),
        findings=(),
        queue_error=queue_error,
    )


def upload_model_version(
    model_id: UUID,
    command: ModelUploadCommand,
    *,
    order_id: UUID | None = None,
) -> ModelUploadOutcome | None:
    model = PrintModel.objects.filter(pk=model_id, owner_id=command.owner_id).first()
    if model is None:
        return None

    basics = _validate_upload_basics(command)
    if isinstance(basics, ModelUploadOutcome):
        return basics
    extension, size, original_name = basics

    version_record = ModelVersion(
        print_model=model,
        order_id=order_id,
        file_name=original_name,
        format=SUPPORTED_FORMATS[extension],
        size_bytes=size,
        is_current=True,
    )
    try:
        version_record.file.save(original_name, command.file, save=False)
    except (BotoCoreError, OSError, ValueError):
        logger.exception("Could not store new version for model %s", model_id)
        return ModelUploadOutcome(
            draft_id=command.draft_id,
            model=None,
            findings=(_finding("E-02", "Не удалось сохранить файл в хранилище."),),
        )

    version_record.storage_key = version_record.file.name
    try:
        with transaction.atomic():
            locked_model = PrintModel.objects.select_for_update().get(pk=model.pk)
            last_version = (
                ModelVersion.objects.filter(print_model=locked_model)
                .aggregate(max_ver=Max("version"))
                .get("max_ver")
                or 0
            )
            ModelVersion.objects.filter(
                print_model=locked_model,
                is_current=True,
            ).update(is_current=False)
            version_record.version = last_version + 1
            version_record.save()

            locked_model.file = version_record.file.name
            locked_model.original_name = original_name
            locked_model.format = version_record.format
            locked_model.size = size
            locked_model.save(
                update_fields=("file", "original_name", "format", "size", "updated_at")
            )
            _schedule_validation(
                locked_model,
                technology=(
                    command.validation_context.technology
                    if command.validation_context
                    else None
                ),
                assembly_selected=(
                    command.validation_context.assembly_selected
                    if command.validation_context
                    else False
                ),
            )
    except DatabaseError:
        version_record.file.delete(save=False)
        raise

    locked_model.refresh_from_db()
    queue_error = (
        locked_model.validation_result.get("error")
        if locked_model.validation_result.get("state") == "queue_error"
        else None
    )
    return ModelUploadOutcome(
        draft_id=command.draft_id,
        model=ModelReceipt(
            model_id=locked_model.pk,
            status=locked_model.status,
            version=version_record.version,
        ),
        findings=(),
        queue_error=queue_error,
    )


def revalidate_model(
    model_id: UUID,
    *,
    owner_id: UUID,
    technology: str | None = None,
    assembly_selected: bool = False,
) -> ModelValidationOutcome | None:
    model = PrintModel.objects.filter(pk=model_id, owner_id=owner_id).first()
    if model is None:
        return None

    _schedule_validation(
        model,
        technology=technology,
        assembly_selected=assembly_selected,
    )
    model.refresh_from_db()
    if model.status == PrintModel.Status.VALIDATED:
        valid = True
    elif model.status == PrintModel.Status.REJECTED:
        valid = False
    else:
        valid = None
    return ModelValidationOutcome(
        valid=valid,
        status=model.status,
        dimensions_mm=(
            (model.width_mm, model.height_mm, model.depth_mm)
            if model.width_mm is not None
            and model.height_mm is not None
            and model.depth_mm is not None
            else None
        ),
        errors=tuple(model.validation_errors),
        queued=model.validation_result.get("state") != "queue_error",
        volume_cm3=model.volume_cm3,
        verdict=model.validation_result.get("verdict"),
    )
