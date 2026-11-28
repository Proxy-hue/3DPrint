from .models import Message


def _extract_version_meta(model_version):
    if model_version is None:
        return None, None
    if isinstance(model_version, dict):
        return model_version.get('id'), model_version.get('version')
    if isinstance(model_version, int):
        return None, model_version
    return getattr(model_version, 'id', None), getattr(model_version, 'version', None)


def post(order, author, text, model_version=None):
    mv_id, mv_num = _extract_version_meta(model_version)
    return Message.objects.create(
        order=order, author=author, text=text,
        model_version_id=mv_id, model_version_num=mv_num,
    )


def list_for(order, since=None):
    qs = Message.objects.filter(order=order).select_related('author')
    if since:
        qs = qs.filter(created_at__gt=since)
    return qs
