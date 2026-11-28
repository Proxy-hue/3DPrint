"""Временный адаптер-интегратор для модулей коллег (models_app, validation, scheduling).

При появлении реальных публичных сервисов в `models_app.services`, `validation.services`
и `scheduling.services` автоматически делегирует вызовы им. До тех пор обеспечивает
минимально необходимый fallback-контур, чтобы модули orders/pricing и клиентский портал
работали и проверялись автономно в чистой ветке.
"""
import importlib
import io
import math
import struct
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace

from django.conf import settings
from django.utils import timezone

from catalog import dto as catalog_dto
from catalog import services as catalog_services

from .exceptions import DomainError

ALLOWED_FORMATS = {'stl': 'STL', 'obj': 'OBJ', '3mf': '3MF'}
MAX_3MF_ENTRIES = 2000
MAX_3MF_RATIO = 100
DEFAULT_THIN = {'FDM': 0.8, 'SLA': 0.4, 'DMLS': 0.6}


def _service_attr(module_path: str, attr: str):
    try:
        mod = importlib.import_module(module_path)
    except ImportError:
        return None
    fn = getattr(mod, attr, None)
    return fn if callable(fn) else None


def _media_root() -> Path:
    root = getattr(settings, 'MEDIA_ROOT', None)
    if root:
        return Path(root)
    return Path(settings.BASE_DIR) / 'media_private'


def _as_obj(data: dict):
    return SimpleNamespace(**data)


# ---------- Временный fallback разбора/хранения моделей (до слияния models_app) ----------
def _check_upload_fallback(file_name: str, data: bytes) -> str:
    if not file_name or '.' not in file_name:
        raise DomainError('E-01: Допустимы только файлы STL, OBJ и 3MF.', 'E-01')
    ext = file_name.rsplit('.', 1)[-1].lower()
    if ext not in ALLOWED_FORMATS:
        raise DomainError('E-01: Допустимы только файлы STL, OBJ и 3MF.', 'E-01')
    fmt = ALLOWED_FORMATS[ext]
    max_bytes = getattr(settings, 'MAX_UPLOAD_BYTES', 50 * 1024 * 1024)
    if len(data) > max_bytes:
        raise DomainError('E-01: Размер файла превышает 50 МБ.', 'E-01')
    if not data or len(data) < 16:
        raise DomainError('E-02: Файл пуст или повреждён.', 'E-02')
    head = data[:16]
    if head.startswith(b'ISO-10303') or head.startswith(b'%PDF') or head.startswith(b'MZ'):
        raise DomainError('E-01: Содержимое файла не соответствует формату STL, OBJ или 3MF.', 'E-01')
    if fmt == '3MF':
        if not data.startswith(b'PK'):
            raise DomainError('E-01: Содержимое файла не соответствует формату 3MF.', 'E-01')
        try:
            with zipfile.ZipFile(io.BytesIO(data), 'r') as zf:
                infos = zf.infolist()
                if not infos or len(infos) > MAX_3MF_ENTRIES:
                    raise DomainError('E-02: Недопустимая структура архива 3MF.', 'E-02')
                max_unpacked = getattr(settings, 'MAX_3MF_UNPACKED_BYTES', 500 * 1024 * 1024)
                total = 0
                total_compressed = 0
                has_model = False
                for i in infos:
                    if i.flag_bits & 0x1:
                        raise DomainError('E-02: Зашифрованные архивы 3MF не поддерживаются.', 'E-02')
                    total += i.file_size
                    total_compressed += i.compress_size
                    if i.compress_size and i.file_size / i.compress_size > MAX_3MF_RATIO and i.file_size > 1024 * 1024:
                        raise DomainError('E-02: Подозрительная степень сжатия в архиве 3MF.', 'E-02')
                    if i.filename.lower().endswith('.model'):
                        has_model = True
                if (
                    total > max_unpacked
                    or (total > 1024 * 1024 and (total_compressed == 0 or total / total_compressed > MAX_3MF_RATIO))
                    or not has_model
                    or zf.testzip() is not None
                ):
                    raise DomainError('E-02: Файл 3MF повреждён.', 'E-02')
        except DomainError:
            raise
        except Exception:
            raise DomainError('E-02: Файл 3MF повреждён или не читается.', 'E-02')
    elif fmt == 'STL':
        is_ascii = data[:512].lstrip().lower().startswith(b'solid') and b'facet' in data[:4096].lower()
        if not is_ascii:
            if len(data) < 84:
                raise DomainError('E-02: Бинарный файл STL обрезан или повреждён.', 'E-02')
            n = struct.unpack('<I', data[80:84])[0]
            if n == 0 or len(data) < 84 + 50 * n:
                raise DomainError('E-02: Бинарный файл STL обрезан или повреждён.', 'E-02')
    else:  # OBJ
        if b'\x00' in data[:2048]:
            raise DomainError('E-01: Содержимое файла не соответствует формату OBJ.', 'E-01')
    return fmt


def _analyze_fallback(data: bytes, fmt: str) -> dict:
    try:
        import numpy as np
        import trimesh
        loaded = trimesh.load(io.BytesIO(data), file_type=fmt.lower(), force=None)
    except Exception:
        raise DomainError('E-02: Не удалось разобрать 3D-сетку модели.', 'E-02')

    meshes = []
    if isinstance(loaded, trimesh.Scene):
        for g in loaded.geometry.values():
            if isinstance(g, trimesh.Trimesh) and len(g.faces) > 0:
                meshes.append(g)
    elif isinstance(loaded, trimesh.Trimesh) and len(loaded.faces) > 0:
        meshes.append(loaded)

    if not meshes:
        raise DomainError('E-02: Модель не содержит полигональной сетки.', 'E-02')

    combined = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
    try:
        body_count = max(len(combined.split(only_watertight=False)), len(meshes), 1)
    except Exception:
        body_count = max(len(meshes), 1)

    watertight = bool(combined.is_watertight)
    repaired = False
    if not watertight:
        try:
            trimesh.repair.fill_holes(combined)
            trimesh.repair.fix_normals(combined)
            repaired = bool(combined.is_watertight)
        except Exception:
            pass

    extents = [float(x) for x in combined.extents] if combined.extents is not None else [0.0, 0.0, 0.0]
    vol_mm3 = abs(float(combined.volume)) if combined.faces is not None and len(combined.faces) > 0 else 0.0
    if (not math.isfinite(vol_mm3) or vol_mm3 <= 0) and all(x > 0 for x in extents):
        vol_mm3 = float(combined.convex_hull.volume) if len(combined.vertices) >= 4 else 0.0
    volume_cm3 = round(vol_mm3 / 1000.0, 4)

    overhang_ratio = 0.0
    try:
        normals = np.asarray(combined.face_normals)
        areas = np.asarray(combined.area_faces)
        total_area = float(np.sum(areas))
        if total_area > 0:
            cos45 = -math.cos(math.radians(45.0))
            zmin = float(combined.bounds[0][2])
            centers_z = np.asarray(combined.triangles_center)[:, 2]
            off_bed = centers_z > zmin + 0.5
            overhang_mask = (normals[:, 2] < cos45) & off_bed
            overhang_ratio = round(float(np.sum(areas[overhang_mask])) / total_area, 4)
    except Exception:
        overhang_ratio = 0.0

    min_dim = min(extents) if extents else 0.0
    area = float(combined.area) if combined.area else 0.0
    thickness = min(min_dim, (vol_mm3 / area) * 2.0) if area else min_dim

    return {
        'bbox': [round(x, 2) for x in extents],
        'volume_cm3': volume_cm3,
        'body_count': int(body_count),
        'analysis': {
            'watertight': watertight,
            'repaired': repaired,
            'min_thickness_mm': round(float(thickness), 4),
            'overhang_ratio': overhang_ratio,
        },
    }


def _save_bytes_fallback(storage_key: str, data: bytes):
    path = _media_root() / storage_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _read_bytes_fallback(storage_key: str) -> bytes:
    path = _media_root() / storage_key
    if not path.exists():
        raise DomainError('Файл модели не найден в хранилище.', 'not_found', 404)
    return path.read_bytes()


# ---------- Публичный интерфейс адаптера моделей ----------
def add_model_version(order, file_name: str, data: bytes):
    ext_fn = _service_attr('models_app.services', 'add_version')
    if ext_fn:
        return ext_fn(order, file_name, data)

    fmt = _check_upload_fallback(file_name, data)
    metrics = _analyze_fallback(data, fmt)
    meta = dict(order.model_meta or {})
    versions = list(meta.get('versions') or [])
    next_ver = max((v.get('version', 0) for v in versions), default=0) + 1
    safe_name = Path(file_name or f'model.{fmt.lower()}').name
    storage_key = f'orders_models/{order.pk}/{uuid.uuid4().hex}.{fmt.lower()}'
    _save_bytes_fallback(storage_key, data)

    bbox = metrics['bbox']
    entry = {
        'id': None,
        'version': next_ver,
        'file_name': safe_name,
        'format': fmt,
        'size_bytes': len(data),
        'storage_key': storage_key,
        'bbox_x': bbox[0],
        'bbox_y': bbox[1],
        'bbox_z': bbox[2],
        'volume_cm3': metrics['volume_cm3'],
        'body_count': metrics['body_count'],
        'analysis': metrics['analysis'],
        'is_current': True,
        'created_at': timezone.now().isoformat(),
    }
    for v in versions:
        v['is_current'] = False
    versions.append(entry)
    meta['versions'] = versions
    meta['current_version'] = next_ver
    order.model_meta = meta
    order.save(update_fields=['model_meta', 'updated_at'])
    return _as_obj(entry)


def current_model_version(order):
    ext_fn = _service_attr('models_app.services', 'current_version')
    if ext_fn:
        mv = ext_fn(order)
        if mv is not None:
            return mv
    versions = (order.model_meta or {}).get('versions') or []
    for v in reversed(versions):
        if v.get('is_current'):
            return _as_obj(v)
    return _as_obj(versions[-1]) if versions else None


def get_model_version(order, version_num: int):
    ext_fn = _service_attr('models_app.services', 'get_version')
    if ext_fn:
        mv = ext_fn(order, version_num)
        if mv is not None:
            return mv
    for v in (order.model_meta or {}).get('versions') or []:
        if int(v.get('version', 0)) == int(version_num):
            return _as_obj(v)
    return None


def clone_model_version(src_order, dst_order):
    ext_fn = _service_attr('models_app.services', 'clone_current')
    if ext_fn:
        return ext_fn(src_order, dst_order)
    mv = current_model_version(src_order)
    if not mv:
        return None
    storage_key = getattr(mv, 'storage_key', '')
    new_key = f'orders_models/{dst_order.pk}/{uuid.uuid4().hex}.{mv.format.lower()}'
    if storage_key:
        src_path = _media_root() / storage_key
        if src_path.exists():
            _save_bytes_fallback(new_key, src_path.read_bytes())
    entry = {
        'id': None,
        'version': 1,
        'file_name': mv.file_name,
        'format': mv.format,
        'size_bytes': mv.size_bytes,
        'storage_key': new_key,
        'bbox_x': mv.bbox_x,
        'bbox_y': mv.bbox_y,
        'bbox_z': mv.bbox_z,
        'volume_cm3': mv.volume_cm3,
        'body_count': mv.body_count,
        'analysis': getattr(mv, 'analysis', {}),
        'is_current': True,
        'created_at': timezone.now().isoformat(),
    }
    dst_order.model_meta = {'current_version': 1, 'versions': [entry], 'validation': None}
    dst_order.save(update_fields=['model_meta', 'updated_at'])
    return _as_obj(entry)


def model_file_info(order, mv):
    ext_fn = _service_attr('models_app.services', 'file_info')
    if ext_fn and getattr(mv, '_state', None) is not None:
        return ext_fn(mv)
    return {
        'url': None,
        'download_url': f'/api/orders/{order.pk}/model/{mv.version}/download',
        'file_name': mv.file_name,
        'format': mv.format,
        'size_bytes': mv.size_bytes,
    }


def read_model_bytes(mv) -> bytes:
    ext_fn = _service_attr('models_app.services', 'read_bytes')
    if ext_fn and getattr(mv, '_state', None) is not None:
        return ext_fn(mv)
    return _read_bytes_fallback(mv.storage_key)


def check_upload_prevalidate(file_name: str, data: bytes) -> str:
    ext_fn = _service_attr('validation.mesh', 'check_upload')
    if ext_fn:
        return ext_fn(file_name, data)
    return _check_upload_fallback(file_name, data)


# ---------- Валидация (делегирует validation.services, иначе использует catalog + геометрию) ----------
def _fits(dims_mm, bbox) -> bool:
    dims_sorted = sorted(float(x) for x in dims_mm)
    b_sorted = sorted(float(x) for x in bbox)
    return all(b_sorted[i] <= dims_sorted[i] + 1e-9 for i in range(3))


def validate_order_model(order, mv):
    ext_fn = _service_attr('validation.services', 'validate')
    if ext_fn and getattr(mv, '_state', None) is not None:
        return ext_fn(order, mv)

    params = catalog_services.get_tariff_params()
    issues = []
    needs_support = False
    bbox = [mv.bbox_x or 0, mv.bbox_y or 0, mv.bbox_z or 0]
    an = getattr(mv, 'analysis', None) or {}
    tech, material = order.technology, order.material
    pps = list(order.post_processings.all())

    if (mv.volume_cm3 or 0) <= 0 or (mv.body_count or 0) < 1:
        issues.append({'code': 'E-03', 'message': 'Модель вырождена: нулевой объём или нет твёрдых тел.'})

    fits_tech = True
    tech_printers = []
    if tech:
        tech_printers = [
            p for p in catalog_services.get_printer_specs(include_inactive=True)
            if p.technology_id == str(tech.pk)
        ]
        if tech_printers and not any(_fits(p.dims_mm, bbox) for p in tech_printers):
            fits_tech = False
            issues.append({
                'code': 'E-04',
                'message': 'Габариты модели превышают область печати всех принтеров выбранной технологии.',
            })

    compat_errors = []
    if tech and material and order.quality_profile and order.color:
        compat_issues = catalog_services.check_compatibility(
            technology=tech, material=material, quality_profile=order.quality_profile,
            color=order.color, post_processings=pps, delivery_method=order.delivery_method,
            pickup_point=order.pickup_point, model_format=mv.format, body_count=mv.body_count,
        )
        for ci in compat_issues:
            compat_errors.append(ci.message)
            issues.append({'code': ci.code, 'message': ci.message})

    if tech and material and fits_tech and not compat_errors:
        mat_spec = catalog_services.get_material_spec(material.pk)
        req_spec = None
        if tech.code == 'DMLS':
            req_spec = catalog_dto.SPEC_METAL
        elif mat_spec.required_specialization != catalog_dto.SPEC_NONE:
            req_spec = mat_spec.required_specialization
        else:
            non_large = [p for p in tech_printers if p.specialization != catalog_dto.SPEC_LARGE_FORMAT]
            if non_large and not any(_fits(p.dims_mm, bbox) for p in non_large):
                req_spec = catalog_dto.SPEC_LARGE_FORMAT

        eligible = [
            p for p in tech_printers
            if p.status == catalog_dto.PRINTER_ACTIVE
            and mat_spec.id in p.material_ids
            and (order.color is None or str(order.color.pk) in mat_spec.color_ids)
            and _fits(p.dims_mm, bbox)
            and (not req_spec or p.specialization == req_spec)
            and (p.specialization == catalog_dto.SPEC_NONE or p.is_main_workshop)
        ]
        if not eligible:
            issues.append({'code': 'E-06', 'message': 'Не найден принтер, удовлетворяющий жёстким условиям.'})

    if an.get('watertight') is False:
        msg = 'Сетка не замкнута (есть отверстия).'
        if an.get('repaired'):
            msg += ' Выполнено автоматическое исправление.'
        issues.append({'code': 'W-01', 'message': msg})

    thin_map = params.get('thin_wall_mm', DEFAULT_THIN)
    if tech and an.get('min_thickness_mm') is not None and an['min_thickness_mm'] < thin_map.get(tech.code, 0.8):
        issues.append({'code': 'W-02', 'message': 'Обнаружены слишком тонкие стенки для выбранной технологии.'})
    if (an.get('overhang_ratio') or 0) > 0.05:
        needs_support = True
        issues.append({'code': 'W-03', 'message': 'Обнаружены нависания более 45°: потребуются поддержки.'})
    has_assembly = any(getattr(p, 'code', '') == 'ASSEMBLY' or p.name == 'Сборка' for p in pps)
    if (mv.body_count or 1) > 1 and not has_assembly:
        issues.append({'code': 'W-04', 'message': 'Модель состоит из нескольких тел, а «Сборка» не выбрана.'})
    if bbox and max(bbox) > 0 and (min(bbox) < 1 or max(bbox) > 1000):
        issues.append({'code': 'W-05', 'message': 'Подозрительные единицы измерения: габарит < 1 мм или > 1000 мм.'})

    if any(i['code'].startswith('E-') for i in issues):
        verdict = 'ERROR'
    elif issues:
        verdict = 'WARNING'
    else:
        verdict = 'OK'

    result = {
        'version': mv.version,
        'verdict': verdict,
        'issues': issues,
        'needs_support': needs_support,
    }
    meta = dict(order.model_meta or {})
    meta['validation'] = result
    order.model_meta = meta
    order.save(update_fields=['model_meta', 'updated_at'])
    return _as_obj(result)


def latest_validation(order, mv):
    if not mv:
        return None
    ext_fn = _service_attr('validation.services', 'latest_for')
    if ext_fn and getattr(mv, '_state', None) is not None:
        return ext_fn(mv)
    vr = (order.model_meta or {}).get('validation')
    if vr and int(vr.get('version', 0)) == int(mv.version):
        return _as_obj(vr)
    return None


# ---------- Планирование (делегирует scheduling.services) ----------
def current_assignment(order):
    fn = _service_attr('scheduling.services', 'current_assignment')
    return fn(order) if fn else None


def clear_assignment(order):
    fn = _service_attr('scheduling.services', 'clear_assignment')
    if fn:
        fn(order)


def recommend_printers(**kwargs):
    fn = _service_attr('scheduling.services', 'recommend')
    if not fn:
        raise DomainError('Модуль планирования scheduling пока не интегрирован.', 'not_implemented', 501)
    return fn(**kwargs)


def get_printer(printer_id):
    fn = _service_attr('scheduling.services', 'get_printer')
    if not fn:
        raise DomainError('Модуль планирования scheduling пока не интегрирован.', 'not_implemented', 501)
    return fn(printer_id)


def assign_printer_job(**kwargs):
    fn = _service_attr('scheduling.services', 'assign')
    if not fn:
        raise DomainError('Модуль планирования scheduling пока не интегрирован.', 'not_implemented', 501)
    return fn(**kwargs)
