import os
from typing import BinaryIO, Protocol

from .contracts import ValidationContext, ValidationFinding, ValidationResult
from .services import SUPPORTED_FORMATS, validate_model_file


class ValidationPublicAPI(Protocol):
    def validate_file(
        self,
        file: BinaryIO,
        filename: str,
        context: ValidationContext | None = None,
    ) -> ValidationResult: ...


def validate_file(
    file: BinaryIO,
    filename: str,
    context: ValidationContext | None = None,
) -> ValidationResult:
    extension = os.path.splitext(filename)[1].lower()
    return validate_model_file(file, extension, context)


__all__ = [
    "SUPPORTED_FORMATS",
    "ValidationContext",
    "ValidationFinding",
    "ValidationPublicAPI",
    "ValidationResult",
    "validate_file",
]
