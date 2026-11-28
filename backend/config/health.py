import django_rq
from django.db import DatabaseError, connections
from drf_spectacular.utils import extend_schema
from redis.exceptions import RedisError
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    @extend_schema(request=None, responses={200: None, 503: None})
    def get(self, request):
        checks: dict[str, str] = {}
        db_ok = True
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            checks["database"] = "ok"
        except DatabaseError:
            checks["database"] = "error"
            db_ok = False

        try:
            connection = django_rq.get_connection("default")
            connection.ping()
            checks["redis"] = "ok"
        except (OSError, RedisError):
            checks["redis"] = "unavailable"

        overall_status = "ok" if db_ok else "degraded"
        http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(
            {
                "status": overall_status,
                "db": checks["database"],
                "checks": checks,
            },
            status=http_status,
        )
