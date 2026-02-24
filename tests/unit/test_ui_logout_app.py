from __future__ import annotations

from fastapi.testclient import TestClient

from apps.ui.logout_app import app
from apps.ui.settings import get_ui_settings


def test_logout_redirects_to_cognito(monkeypatch):
    monkeypatch.setenv(
        "UI_COGNITO_HOSTED_UI_BASE",
        "https://example.auth.us-west-2.amazoncognito.com",
    )
    monkeypatch.setenv("UI_COGNITO_CLIENT_ID", "client-123")
    monkeypatch.setenv("UI_PUBLIC_BASE_URL", "https://ui.example.com")
    get_ui_settings.cache_clear()

    client = TestClient(app)
    resp = client.get("/auth/logout", follow_redirects=False)

    assert resp.status_code == 302
    assert (
        resp.headers["location"]
        == "https://example.auth.us-west-2.amazoncognito.com/logout"
        "?client_id=client-123"
        "&logout_uri=https%3A%2F%2Fui.example.com%2F"
    )


def test_logout_sets_alb_cookie_expiration(monkeypatch):
    monkeypatch.setenv("UI_PUBLIC_BASE_URL", "https://ui.example.com")
    get_ui_settings.cache_clear()

    client = TestClient(app)
    resp = client.get("/auth/logout", follow_redirects=False)

    set_cookie_header = "\n".join(resp.headers.get_list("set-cookie"))
    assert "AWSELBAuthSessionCookie=" in set_cookie_header
    assert "AWSALBAuthNonce=" in set_cookie_header
