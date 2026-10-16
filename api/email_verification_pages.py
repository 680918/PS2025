"""Explicit email confirmations; no public token issuing, mail sending or login."""

import hashlib
import hmac
import re
import secrets
import sqlite3
from time import time
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse

from api.public_pages import (
    render_registration_verification_page,
    render_verification_page,
)
from security.email_verification import (
    confirm_email_verification,
    confirm_registration_verification,
)


_PATH = "/web/verify-email"
_COOKIE = "coach_email_confirmation"
_REGISTRATION_PATH = "/web/verify-registration"
_REGISTRATION_COOKIE = "coach_registration_confirmation"
_LIFETIME = 600
_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}")
_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'self'; form-action 'self'; "
        "base-uri 'none'; frame-ancestors 'none'"
    ),
}


def _valid_token(value):
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def register_email_verification_pages(app, repository):
    _register_confirmation_pages(
        app,
        path=_PATH,
        cookie_name=_COOKIE,
        render_page=render_verification_page,
        confirm=lambda token: confirm_email_verification(repository, token),
    )


def register_registration_verification_pages(app, repository):
    _register_confirmation_pages(
        app,
        path=_REGISTRATION_PATH,
        cookie_name=_REGISTRATION_COOKIE,
        render_page=render_registration_verification_page,
        confirm=lambda token: confirm_registration_verification(repository, token),
    )


def _register_confirmation_pages(app, *, path, cookie_name, render_page, confirm):
    # Ephemeral per-process signing key: a restart requires reopening the email,
    # while the actual verification token remains valid until its stored expiry.
    signing_key = secrets.token_bytes(32)

    def signature(token, nonce, expires):
        payload = f"{path}.{token}.{nonce}.{expires}".encode("ascii")
        return hmac.new(signing_key, payload, hashlib.sha256).hexdigest()

    def response(state, code=200, **fields):
        return HTMLResponse(
            render_page(state, **fields),
            status_code=code,
            headers=_HEADERS,
        )

    @app.get(path, response_class=HTMLResponse, include_in_schema=False)
    def verification_page(request: Request):
        tokens = request.query_params.getlist("token")
        if len(tokens) != 1 or not _valid_token(tokens[0]):
            return response("invalid", 400)
        token = tokens[0]
        nonce = secrets.token_urlsafe(32)
        expires = str(int(time()) + _LIFETIME)
        cookie = f"{nonce}.{expires}.{signature(token, nonce, expires)}"
        page = response("confirm", token=token, csrf=nonce)
        page.set_cookie(
            cookie_name,
            cookie,
            max_age=_LIFETIME,
            path=path,
            secure=request.url.scheme == "https",
            httponly=True,
            samesite="strict",
        )
        return page

    @app.post(path, response_class=HTMLResponse, include_in_schema=False)
    async def verification_confirm(request: Request):
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            # no-referrer can make a legitimate browser form POST use Origin:
            # null. It still MUST pass the signed cookie + form-token checks.
            origin not in {None, "null"}
            and origin != f"{request.url.scheme}://{request.url.netloc}"
        ):
            return response("retry", 403)
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            return response("invalid", 400)
        # Bound the body before parsing; never return FastAPI's input echo.
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 2048:
                return response("invalid", 400)
            body.extend(chunk)
        try:
            fields = parse_qs(
                body.decode("ascii"),
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=2,
            )
        except (ValueError, UnicodeError):
            return response("invalid", 400)
        if set(fields) != {"token", "csrf"} or any(
            len(v) != 1 for v in fields.values()
        ):
            return response("invalid", 400)
        token, csrf = fields["token"][0], fields["csrf"][0]
        if not _valid_token(token) or not _valid_token(csrf):
            return response("invalid", 400)
        cookie = request.cookies.get(cookie_name, "")
        parts = cookie.split(".")
        if len(parts) != 3:
            return response("retry", 403)
        nonce, expires, signed = parts
        if (
            not _valid_token(nonce)
            or not expires.isascii()
            or not expires.isdigit()
            or len(expires) != 10
            or not re.fullmatch(r"[0-9a-f]{64}", signed)
            or not hmac.compare_digest(nonce, csrf)
            or not hmac.compare_digest(signature(token, nonce, expires), signed)
            or not int(time()) < int(expires) <= int(time()) + _LIFETIME
        ):
            return response("retry", 403)
        try:
            verified_user_id = confirm(token)
        except sqlite3.Error:
            # Do not expose database details or mistake a storage failure for an
            # invalid link. The user can retry from the original email.
            return response("unavailable", 503)
        page = response(
            "success" if verified_user_id is not None else "invalid",
            200 if verified_user_id is not None else 400,
        )
        page.delete_cookie(
            cookie_name,
            path=path,
            secure=request.url.scheme == "https",
            httponly=True,
            samesite="strict",
        )
        return page
