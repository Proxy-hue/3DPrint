from dataclasses import asdict

from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsManagerOrAdmin

from . import services
from .serializers import LoadSerializer


class LoadView(APIView):
    """Плановая загрузка принтеров и цехов (F-MGR-06): М, А."""

    permission_classes = [IsManagerOrAdmin]

    @extend_schema(responses=LoadSerializer)
    def get(self, request):
        data = services.get_load()
        data['printers'] = [asdict(p) for p in data['printers']]
        data['workshops'] = [asdict(w) for w in data['workshops']]
        return Response(LoadSerializer(data).data)
