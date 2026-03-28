import os
from datetime import datetime

import pytest
from starlette.requests import Request

os.environ["DEBUG"] = "false"

from src.api.routes.auth.utils import _get_frontend_url
from src.infra.auth.oauth import OAuthService, OAuthUserInfo
from src.kernel.schemas.user import OAuthProvider, User


def _build_request(headers: dict[str, str]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/auth/oauth/google/callback",
        "headers": [(key.lower().encode(), value.encode()) for key, value in headers.items()],
        "scheme": "http",
        "server": ("backend", 8000),
        "client": ("127.0.0.1", 12345),
        "query_string": b"",
    }
    return Request(scope)


def test_get_frontend_url_uses_forwarded_proto_with_host_header():
    request = _build_request(
        {
            "host": "app.example.com",
            "x-forwarded-proto": "https",
        }
    )

    assert _get_frontend_url(request) == "https://app.example.com"


@pytest.mark.asyncio
async def test_handle_callback_does_not_require_process_local_state(monkeypatch: pytest.MonkeyPatch):
    service = OAuthService()

    class DummyClient:
        async def fetch_token(self, token_url, code, redirect_uri):
            assert token_url == "https://oauth2.googleapis.com/token"
            assert code == "auth-code"
            assert redirect_uri == "https://app.example.com/api/auth/oauth/google/callback"
            return {"access_token": "google-token"}

    async def fake_get_user_info(provider, token):
        assert provider == OAuthProvider.GOOGLE
        assert token == {"access_token": "google-token"}
        return OAuthUserInfo(
            provider=OAuthProvider.GOOGLE,
            oauth_id="google-user-1",
            email="user@example.com",
            username="oauth-user",
        )

    async def fake_find_or_create_user(user_info):
        assert user_info.oauth_id == "google-user-1"
        return User(
            id="user-1",
            username="oauth-user",
            email="user@example.com",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

    monkeypatch.setattr(service, "is_provider_enabled", lambda provider: True)
    monkeypatch.setattr(service, "_get_client", lambda provider: DummyClient())
    monkeypatch.setattr(service, "_get_user_info", fake_get_user_info)
    monkeypatch.setattr(service, "_find_or_create_user", fake_find_or_create_user)

    token = await service.handle_callback(
        OAuthProvider.GOOGLE,
        "auth-code",
        "state-from-redis",
        "https://app.example.com/api/auth/oauth/google/callback",
    )

    assert token is not None
    assert token.access_token
    assert token.refresh_token
