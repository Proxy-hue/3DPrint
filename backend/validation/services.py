import os
import struct
import zipfile
import zlib
from io import BytesIO
from typing import BinaryIO

import numpy as np
import trimesh
from lxml.etree import XMLSyntaxError

from .contracts import (
    ValidationContext,
    ValidationFinding,
    ValidationResult,
)


MAX_FILE_SIZE = 50 * 1024 * 1024
MAX_3MF_UNCOMPRESSED_SIZE = 256 * 1024 * 1024
MAX_THICKNESS_SAMPLES = 2048
OVERHANG_THRESHOLD_DEGREES = 45.0
SUPPORTED_FORMATS = {
    ".stl": "stl",
    ".obj": "obj",
    ".3mf": "3mf",
}
MIN_WALL_THICKNESS_MM = {
    "FDM": 0.8,
    "SLA": 0.4,
    "DMLS": 0.6,
}
OBJ_RECORDS = {"v", "vt", "vn", "f", "o", "g", "mtllib", "usemtl", "s"}


def _finding(code: str, severity: str, message: str) -> ValidationFinding:
    return ValidationFinding(code=code, severity=severity, message=message)


def _result(
    findings: list[ValidationFinding],
    dimensions_mm: tuple[float, float, float] | None = None,
    *,
    needs_support: bool = False,
) -> ValidationResult:
    return ValidationResult(
        valid=not any(finding.severity == "error" for finding in findings),
        findings=tuple(findings),
        dimensions_mm=dimensions_mm,
        needs_support=needs_support,
        support_factor=1.0 if needs_support else 0.0,
    )


def _detect_file_type(content: bytes) -> str | None:
    if zipfile.is_zipfile(BytesIO(content)):
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if "3D/3dmodel.model" in archive.namelist():
                    return "3mf"
                return "zip"
        except (OSError, zipfile.BadZipFile):
            return "zip"

    stripped = content.lstrip()
    lowered = stripped.lower()
    if lowered.startswith(b"solid") and (
        b"facet" in lowered or b"vertex" in lowered
    ):
        return "stl"

    if len(content) >= 84:
        facet_count = struct.unpack_from("<I", content, 80)[0]
        expected_size = 84 + facet_count * 50
        if expected_size <= len(content) and (
            facet_count > 0 or len(content) == 84
        ):
            return "stl"

    if stripped.startswith(b"ply"):
        return "ply"

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None

    for line in text.splitlines():
        fields = line.strip().split()
        if fields and fields[0] in OBJ_RECORDS:
            return "obj"
        if fields and not fields[0].startswith("#"):
            break
    return None


def _validate_3mf_archive(content: bytes) -> ValidationFinding | None:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            members = archive.infolist()
            expanded_size = sum(member.file_size for member in members)
            if expanded_size > MAX_3MF_UNCOMPRESSED_SIZE:
                return _finding(
                    "E-02",
                    "error",
                    "Объём распакованных данных 3MF превышает 256 МиБ.",
                )
            if "3D/3dmodel.model" not in archive.namelist():
                return _finding(
                    "E-02",
                    "error",
                    "В архиве 3MF отсутствует 3D/3dmodel.model.",
                )
            corrupt_member = archive.testzip()
            if corrupt_member is not None:
                return _finding(
                    "E-02",
                    "error",
                    f"Архив 3MF повреждён: {corrupt_member}.",
                )
    except (
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        zipfile.LargeZipFile,
        zlib.error,
    ):
        return _finding("E-02", "error", "Файл 3MF повреждён или не читается.")
    return None


def _load_mesh(
    content: bytes,
    file_type: str,
) -> trimesh.Trimesh | trimesh.points.PointCloud | None:
    loaded = trimesh.load(
        file_obj=BytesIO(content),
        file_type=file_type,
        force="scene",
        process=True,
    )
    if isinstance(loaded, trimesh.Scene):
        geometry = loaded.to_geometry()
        if isinstance(geometry, (trimesh.Trimesh, trimesh.points.PointCloud)):
            return geometry
        return None
    if isinstance(loaded, trimesh.Trimesh):
        return loaded
    if isinstance(loaded, trimesh.points.PointCloud):
        return loaded
    return None


def _scale_3mf_to_mm(mesh: trimesh.Trimesh) -> float | None:
    source_unit = mesh.metadata.get("units") or "millimeter"
    try:
        scale = trimesh.units.unit_conversion(str(source_unit), "millimeter")
    except (KeyError, TypeError, ValueError):
        return None
    if not np.isfinite(scale) or scale <= 0:
        return None
    mesh.apply_scale(scale)
    return float(scale)


def _minimum_sampled_thickness(mesh: trimesh.Trimesh) -> float | None:
    if not mesh.is_watertight or len(mesh.faces) == 0:
        return None

    sample_count = min(len(mesh.faces), MAX_THICKNESS_SAMPLES)
    indices = np.linspace(
        0,
        len(mesh.faces) - 1,
        num=sample_count,
        dtype=np.int64,
    )
    thickness = trimesh.proximity.thickness(
        mesh,
        mesh.triangles_center[indices],
        normals=mesh.face_normals[indices],
        method="ray",
    )
    finite_thickness = thickness[np.isfinite(thickness)]
    if len(finite_thickness) == 0:
        return None
    return float(np.min(finite_thickness))


def _has_supported_overhang(mesh: trimesh.Trimesh) -> bool:
    if len(mesh.faces) == 0:
        return False

    normals_z = mesh.face_normals[:, 2]
    face_centers_z = mesh.triangles_center[:, 2]
    minimum_z = float(mesh.bounds[0, 2])
    extents = np.asarray(mesh.extents, dtype=np.float64)
    contact_tolerance = max(1e-6, float(np.max(extents)) * 1e-6)
    above_build_plate = face_centers_z > minimum_z + contact_tolerance
    downward_faces = (normals_z < 0) & above_build_plate
    if not np.any(downward_faces):
        return False

    face_angle_from_bed = np.degrees(
        np.arccos(np.clip(-normals_z[downward_faces], 0.0, 1.0))
    )
    overhang_angle = 90.0 - face_angle_from_bed
    return bool(np.any(overhang_angle > OVERHANG_THRESHOLD_DEGREES))


def validate_model_file(
    file: BinaryIO,
    extension: str | None = None,
    context: ValidationContext | None = None,
) -> ValidationResult:
    extension = (
        extension or os.path.splitext(getattr(file, "name", ""))[1]
    ).lower()
    if extension not in SUPPORTED_FORMATS:
        return _result([
            _finding(
                "E-01",
                "error",
                "Поддерживаются только файлы STL, OBJ и 3MF.",
            )
        ])

    reported_size = getattr(file, "size", None)
    if isinstance(reported_size, int) and reported_size > MAX_FILE_SIZE:
        return _result([
            _finding("E-01", "error", "Размер файла превышает 50 МиБ.")
        ])

    try:
        file.seek(0)
        content = file.read(MAX_FILE_SIZE + 1)
        file.seek(0)
    except (AttributeError, OSError, TypeError, ValueError):
        return _result([
            _finding("E-02", "error", "Файл не читается.")
        ])
    if not isinstance(content, bytes):
        return _result([
            _finding("E-02", "error", "Файл должен быть передан в бинарном виде.")
        ])
    if len(content) > MAX_FILE_SIZE:
        return _result([
            _finding("E-01", "error", "Размер файла превышает 50 МиБ.")
        ])
    if not content:
        return _result([
            _finding("E-02", "error", "Файл пуст.")
        ])

    detected_type = _detect_file_type(content)
    if detected_type == "zip" and extension == ".3mf":
        return _result([
            _finding("E-02", "error", "Архив 3MF не содержит модель.")
        ])
    if detected_type is None:
        return _result([
            _finding("E-02", "error", "Файл повреждён или не содержит модель.")
        ])
    if detected_type != SUPPORTED_FORMATS[extension]:
        return _result([
            _finding(
                "E-01",
                "error",
                "Сигнатура файла не соответствует расширению.",
            )
        ])

    if extension == ".3mf":
        archive_finding = _validate_3mf_archive(content)
        if archive_finding is not None:
            return _result([archive_finding])

    try:
        mesh = _load_mesh(content, extension[1:])
    except (
        IndexError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
        XMLSyntaxError,
        zipfile.BadZipFile,
        struct.error,
    ):
        return _result([
            _finding("E-02", "error", "Файл повреждён или не может быть разобран.")
        ])
    if mesh is None:
        return _result([
            _finding("E-02", "error", "Не удалось получить геометрию модели.")
        ])

    if extension == ".3mf" and _scale_3mf_to_mm(mesh) is None:
        return _result([
            _finding("E-02", "error", "В 3MF указана неизвестная единица измерения.")
        ])

    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    if not np.isfinite(vertices).all():
        return _result([
            _finding("E-02", "error", "Координаты модели содержат NaN или Infinity.")
        ])
    if isinstance(mesh, trimesh.points.PointCloud):
        dimensions_mm = None
        if vertices.size:
            dimensions_mm = tuple(
                float(dimension) for dimension in np.ptp(vertices, axis=0)
            )
        return _result(
            [
                _finding(
                    "E-03",
                    "error",
                    "Модель вырождена: в файле нет ни одного тела.",
                )
            ],
            dimensions_mm,
        )

    findings: list[ValidationFinding] = []
    if len(mesh.faces) == 0:
        return _result([
            _finding(
                "E-03",
                "error",
                "Модель вырождена: в файле нет ни одного тела.",
            )
        ])

    if not mesh.is_watertight:
        findings.append(
            _finding(
                "W-01",
                "warning",
                "Сетка не замкнута; выполнена попытка заполнения отверстий в памяти.",
            )
        )
        trimesh.repair.fill_holes(mesh)
        trimesh.repair.fix_normals(mesh)

    extents = np.asarray(mesh.extents, dtype=np.float64)
    if not np.isfinite(extents).all():
        return _result([
            _finding("E-02", "error", "Габариты модели не удалось вычислить.")
        ])
    dimensions_mm = tuple(float(dimension) for dimension in extents)
    body_count = len(mesh.split(only_watertight=False))
    volume = float(mesh.volume)
    if body_count == 0 or not np.isfinite(volume) or volume <= 0:
        findings.append(
            _finding(
                "E-03",
                "error",
                "Модель вырождена: объём должен быть положительным и присутствовать хотя бы один body.",
            )
        )
        return _result(findings, dimensions_mm)

    if body_count > 1 and not (context and context.assembly_selected):
        findings.append(
            _finding(
                "W-04",
                "warning",
                "В файле несколько несвязанных тел, а сборка не выбрана.",
            )
        )

    if min(dimensions_mm) < 1 or max(dimensions_mm) > 1000:
        findings.append(
            _finding(
                "W-05",
                "warning",
                "Возможна ошибка единиц измерения: габарит меньше 1 мм или больше 1000 мм.",
            )
        )

    technology = context.technology.upper() if context and context.technology else None
    thickness_threshold = MIN_WALL_THICKNESS_MM.get(technology or "")
    if thickness_threshold is not None:
        minimum_thickness = _minimum_sampled_thickness(mesh)
        if minimum_thickness is not None and minimum_thickness < thickness_threshold:
            findings.append(
                _finding(
                    "W-02",
                    "warning",
                    (
                        "Подозрение на тонкие стенки: оценка "
                        f"{minimum_thickness:.2f} мм меньше порога "
                        f"{thickness_threshold:.1f} мм для {technology}."
                    ),
                )
            )

    needs_support = _has_supported_overhang(mesh)
    if needs_support:
        findings.append(
            _finding(
                "W-03",
                "warning",
                "Обнаружены нависания более 45°; могут потребоваться поддержки.",
            )
        )

    return _result(findings, dimensions_mm, needs_support=needs_support)
