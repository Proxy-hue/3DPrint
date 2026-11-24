import os
import struct
import zipfile
import xml.etree.ElementTree as ET

from models.models import PrintModel


MAX_FILE_SIZE = 50 * 1024 * 1024
SUPPORTED_FORMATS = {
    ".stl": PrintModel.Format.STL,
    ".obj": PrintModel.Format.OBJ,
    ".3mf": PrintModel.Format.THREE_MF,
}


def _bounds(points):
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    zs = [point[2] for point in points]
    return (
        max(xs) - min(xs),
        max(ys) - min(ys),
        max(zs) - min(zs),
    )


def validate_binary_stl(content):
    if len(content) < 84:
        return [], None
    facet_count = struct.unpack_from("<I", content, 80)[0]
    expected_size = 84 + facet_count * 50
    if facet_count == 0:
        return ["STL-файл не содержит треугольников."], None
    if len(content) < expected_size:
        return ["STL-файл обрезан или поврежден."], None

    points = []
    for index in range(facet_count):
        offset = 84 + index * 50
        try:
            values = struct.unpack_from("<12fH", content, offset)
        except struct.error:
            return ["STL-файл содержит некорректные треугольники."], None
        points.extend((values[3], values[4], values[5]),)
        points.extend((values[6], values[7], values[8]),)
        points.extend((values[9], values[10], values[11]),)
    return [], _bounds(points)


def validate_ascii_stl(content):
    points = []
    for line in content.splitlines():
        fields = line.strip().split()
        if len(fields) == 4 and fields[0].lower() in (b"vertex", "vertex"):
            try:
                points.append(tuple(float(value) for value in fields[1:4]))
            except ValueError:
                return ["STL-файл содержит некорректные координаты."], None
    if not points:
        return ["STL-файл не содержит треугольников."], None
    return [], _bounds(points)


def validate_stl(file):
    content = file.read()
    file.seek(0)
    stripped = content.lstrip().lower()
    if stripped.startswith(b"solid"):
        return validate_ascii_stl(content)
    return validate_binary_stl(content)


def validate_obj(file):
    points = []
    errors = []
    try:
        content = file.read(MAX_FILE_SIZE + 1)
    except OSError:
        return ["Не удалось прочитать OBJ-файл."], None
    finally:
        file.seek(0)
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return ["Файл OBJ должен содержать текст в кодировке UTF-8."], None

    for line in text.splitlines():
        fields = line.strip().split()
        if fields and fields[0] == "v" and len(fields) >= 4:
            try:
                points.append(tuple(float(value) for value in fields[1:4]))
            except ValueError:
                errors.append("OBJ-файл содержит некорректные координаты.")
                break
    if not points:
        errors.append("OBJ-файл не содержит вершин.")
    return errors, _bounds(points)


def validate_3mf(file):
    try:
        with zipfile.ZipFile(file) as archive:
            bad_member = archive.testzip()
            if bad_member:
                return [f"Архив 3MF поврежден: {bad_member}."], None

            model_member = "3D/3dmodel.model"
            if model_member not in archive.namelist():
                return ["В архиве 3MF отсутствует файл 3D/3dmodel.model."], None

            try:
                root = ET.fromstring(archive.read(model_member))
            except ET.ParseError:
                return ["Файл 3dmodel.model содержит некорректный XML."], None

            points = []
            for vertex in root.iter():
                if vertex.tag.rsplit("}", 1)[-1] != "vertex":
                    continue
                try:
                    points.append((
                        float(vertex.attrib["x"]),
                        float(vertex.attrib["y"]),
                        float(vertex.attrib["z"]),
                    ))
                except (KeyError, ValueError):
                    return ["Файл 3MF содержит некорректные координаты."], None
            if not points:
                return ["Файл 3MF не содержит вершин."], None
            return [], _bounds(points)
    except (zipfile.BadZipFile, OSError):
        return ["Файл 3MF не является корректным ZIP-архивом."], None
    finally:
        file.seek(0)


def validate_model_file(file, extension=None):
    extension = extension or os.path.splitext(getattr(file, "name", ""))[1].lower()
    size = getattr(file, "size", None)
    if size is None:
        try:
            file.seek(0, os.SEEK_END)
            size = file.tell()
            file.seek(0)
        except (AttributeError, OSError):
            size = 0

    errors = []
    if size == 0:
        errors.append("Файл пуст.")
    if size > MAX_FILE_SIZE:
        errors.append("Размер файла не должен превышать 50 МБ.")
    if extension not in SUPPORTED_FORMATS:
        errors.append("Поддерживаются только STL, OBJ и 3MF.")
    if errors:
        return {"valid": False, "errors": errors, "dimensions": None}

    if extension == ".stl":
        geometry_errors, dimensions = validate_stl(file)
    elif extension == ".obj":
        geometry_errors, dimensions = validate_obj(file)
    else:
        geometry_errors, dimensions = validate_3mf(file)

    if dimensions:
        width, height, depth = dimensions
        if width <= 0 or height <= 0 or depth <= 0:
            geometry_errors.append("Габариты модели должны быть больше нуля.")
    else:
        dimensions = None

    return {
        "valid": not geometry_errors,
        "errors": geometry_errors,
        "dimensions": dimensions,
    }
