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


def test_classify_ui_error_for_policy_block():
    level, message = ui_app._classify_ui_error(
        error_message="Input blocked by safety policy: SAFETY_PROFANITY.",
        error_code="POLICY_BLOCKED_INPUT",
    )
    assert level == "warning"
    assert "blocked by safety policy" in message.lower()


def test_classify_ui_error_for_policy_block_hate_category():
    level, message = ui_app._classify_ui_error(
        error_message="Input blocked by safety policy: SAFETY_HATE_CONTENT.",
        error_code="POLICY_BLOCKED_INPUT",
        blocked_category="hate_content",
        reason_codes=["SAFETY_HATE_CONTENT"],
    )
    assert level == "warning"
    assert "discriminatory" in message.lower()
    assert "SAFETY_HATE_CONTENT" in message


def test_classify_ui_error_for_safety_unavailable():
    level, message = ui_app._classify_ui_error(
        error_message="Safety checks unavailable.",
        error_code="SAFETY_UNAVAILABLE",
    )
    assert level == "error"
    assert "temporarily unavailable" in message.lower()
