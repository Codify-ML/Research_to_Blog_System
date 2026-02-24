from __future__ import annotations

from urllib.parse import quote

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from apps.ui.settings import get_ui_settings

ALB_COOKIE_BASE_NAMES = ("AWSELBAuthSessionCookie", "AWSALBAuthNonce")
ALB_COOKIE_SUFFIXES = 8

app = FastAPI(title="UI Logout Service")


def _build_cognito_logout_url() -> str:
    settings = get_ui_settings()
    public_base = settings.ui_public_base_url.rstrip("/")
    fallback_url = f"{public_base}/"

    if (
        not settings.ui_cognito_hosted_ui_base
        or not settings.ui_cognito_client_id
    ):
        return fallback_url

    hosted_ui_base = settings.ui_cognito_hosted_ui_base.rstrip("/")
    client_id = quote(settings.ui_cognito_client_id, safe="")
    logout_uri = quote(fallback_url, safe="")
    return (
        f"{hosted_ui_base}/logout"
        f"?client_id={client_id}"
        f"&logout_uri={logout_uri}"
    )


def _expire_alb_cookies(response: RedirectResponse) -> None:
    cookie_names: list[str] = []
    for base in ALB_COOKIE_BASE_NAMES:
        cookie_names.append(base)
        for idx in range(ALB_COOKIE_SUFFIXES):
            cookie_names.append(f"{base}-{idx}")

    for name in cookie_names:
        response.set_cookie(
            key=name,
            value="",
            max_age=0,
            expires=0,
            path="/",
            secure=True,
            httponly=True,
            samesite="none",
        )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(
        url=_build_cognito_logout_url(),
        status_code=302,
    )
    _expire_alb_cookies(response)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response
