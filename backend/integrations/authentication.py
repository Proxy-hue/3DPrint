import hmac

from django.utils import timezone
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import authentication, exceptions

from .contracts import ApiClientPrincipal
from .models import ApiClient, hash_api_key


def _extract_api_key(request) -> str | None:
    header_key = request.META.get("HTTP_X_API_KEY")
    if header_key:
        stripped = header_key.strip()
        return stripped or None

    auth_header = authentication.get_authorization_header(request).decode("utf-8", errors="ignore")
    if not auth_header:
        return None
    parts = auth_header.split(None, 1)
    if len(parts) == 2 and parts[0].lower() == "api-key":
        stripped = parts[1].strip()
        return stripped or None
    return None


class ApiKeyAuthentication(authentication.BaseAuthentication):
    keyword = "Api-Key"

    def authenticate(self, request):
        raw_key = _extract_api_key(request)
        if raw_key is None:
            return None

        candidate_hash = hash_api_key(raw_key)
        client = ApiClient.objects.filter(api_key_hash=candidate_hash).first()
        if client is None or not hmac.compare_digest(client.api_key_hash, candidate_hash):
            raise exceptions.AuthenticationFailed(
                {
                    "code": "INVALID_API_KEY",
                    "message": "Недействительный API-ключ.",
                }
            )
        if not client.is_active:
            raise exceptions.AuthenticationFailed(
                {
                    "code": "REVOKED_API_KEY",
                    "message": "API-ключ отозван или деактивирован.",
                }
            )

        ApiClient.objects.filter(pk=client.pk).update(last_used_at=timezone.now())
        principal = ApiClientPrincipal(
            client_id=client.pk,
            name=client.name,
            scopes=frozenset(client.scopes or ()),
        )
        return principal, client

    def authenticate_header(self, request) -> str:
        return self.keyword


class ApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "integrations.authentication.ApiKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
