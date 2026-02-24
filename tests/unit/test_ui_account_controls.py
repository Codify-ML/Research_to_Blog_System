from __future__ import annotations

from apps.ui import app as ui_app
from apps.ui.settings import get_ui_settings


def test_account_urls_absent_when_cognito_not_configured(monkeypatch):
    monkeypatch.delenv("UI_COGNITO_HOSTED_UI_BASE", raising=False)
    monkeypatch.delenv("UI_COGNITO_CLIENT_ID", raising=False)
    get_ui_settings.cache_clear()

    assert ui_app._build_signout_url() is None


def test_signout_url_is_constructed(monkeypatch):
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

    sign_out_url = ui_app._build_signout_url()
    assert sign_out_url == "https://ui.example.com/auth/logout"
