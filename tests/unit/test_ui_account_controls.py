from __future__ import annotations

from apps.ui import app as ui_app
from apps.ui.settings import get_ui_settings


def test_account_urls_absent_when_cognito_not_configured(monkeypatch):
    monkeypatch.delenv("UI_COGNITO_HOSTED_UI_BASE", raising=False)
    monkeypatch.delenv("UI_COGNITO_CLIENT_ID", raising=False)
    get_ui_settings.cache_clear()

    assert ui_app._build_account_urls() is None


def test_account_urls_are_constructed(monkeypatch):
    monkeypatch.setenv(
        "UI_COGNITO_HOSTED_UI_BASE",
        "https://example.auth.us-west-2.amazoncognito.com",
    )
    monkeypatch.setenv("UI_COGNITO_CLIENT_ID", "client-123")
    monkeypatch.setenv(
        "UI_PUBLIC_BASE_URL",
        "https://ui.example.com",
    )
    get_ui_settings.cache_clear()

    urls = ui_app._build_account_urls()
    assert urls is not None
    sign_out_url, switch_account_url = urls
    assert "/logout?" in sign_out_url
    assert "client_id=client-123" in sign_out_url
    assert "logout_uri=https%3A%2F%2Fui.example.com%2F" in sign_out_url
    assert "/oauth2/authorize?" in switch_account_url
    assert "prompt=login" in switch_account_url
