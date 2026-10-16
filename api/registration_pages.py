"""Registration form preview: bounded, read-only validation with honest status."""

import hashlib
import hmac
import re
import secrets
from time import time
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse

from api.public_pages import (
    render_registration_page,
    render_registration_rate_limited_page,
    render_registration_security_retry_page,
    render_registration_waiting_page,
)
from security.registration_validation import validate_registration_fields
from security.registration_rate_limit import RegistrationRateLimiter


_COOKIE = "coach_registration_form"
_COOKIE_PATH = "/web"
_FORM_LIFETIME = 1800
_GET_PER_CLIENT = 30
_GET_TOTAL = 240
_POST_PER_CLIENT = 10
_POST_TOTAL = 120
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


def register_registration_preview(app):
    # Single-process local development. Restarting requires reopening the form.
    signing_key = secrets.token_bytes(32)
    page_limit = RegistrationRateLimiter(
        per_client_limit=_GET_PER_CLIENT, total_limit=_GET_TOTAL
    )
    submit_limit = RegistrationRateLimiter(
        per_client_limit=_POST_PER_CLIENT, total_limit=_POST_TOTAL
    )

    def limited_response(request, limiter):
        # Use the transport peer, never arbitrary Forwarded/X-Forwarded-For
        # headers or a resettable browser cookie. Local runner disables proxies.
        client_key = request.client.host if request.client else "unknown"
        wait = limiter.admit(client_key)
        if wait:
            return HTMLResponse(
                render_registration_rate_limited_page(wait),
                status_code=429,
                headers={**_HEADERS, "Retry-After": str(wait)},
            )
        return None

    def signature(nonce, expires):
        payload = f"registration-form.{nonce}.{expires}".encode("ascii")
        return hmac.new(signing_key, payload, hashlib.sha256).hexdigest()

    def browser_context(request):
        cookie = request.cookies.get(_COOKIE, "")
        if len(cookie) > 200:
            return None
        parts = cookie.split(".")
        if len(parts) != 3:
            return None
        nonce, expires, signed = parts
        if (
            _TOKEN.fullmatch(nonce) is None
            or not re.fullmatch(r"[0-9]{10}", expires)
            or not re.fullmatch(r"[0-9a-f]{64}", signed)
            or not hmac.compare_digest(signature(nonce, expires), signed)
            or not int(time()) < int(expires) <= int(time()) + _FORM_LIFETIME
        ):
            return None
        return nonce

    def form_response(csrf, *, code=200, **fields):
        return HTMLResponse(
            render_registration_page(csrf=csrf, **fields),
            status_code=code,
            headers=_HEADERS,
        )

    def form_error(csrf):
        return form_response(
            csrf, code=400, form_error="填写内容无法读取，请重新填写后提交。"
        )

    def security_retry():
        return HTMLResponse(
            render_registration_security_retry_page(),
            status_code=403,
            headers=_HEADERS,
        )

    @app.get("/web/register", response_class=HTMLResponse, include_in_schema=False)
    def registration_form(request: Request):
        limited = limited_response(request, page_limit)
        if limited is not None:
            return limited
        csrf = browser_context(request)
        if csrf is not None:
            # Keep valid contexts stable so opening another tab does not erase
            # the form someone is already filling. GET does not extend expiry.
            return form_response(csrf)
        csrf = secrets.token_urlsafe(32)
        expires = str(int(time()) + _FORM_LIFETIME)
        page = form_response(csrf)
        page.set_cookie(
            _COOKIE,
            f"{csrf}.{expires}.{signature(csrf, expires)}",
            max_age=_FORM_LIFETIME,
            path=_COOKIE_PATH,
            secure=request.url.scheme == "https",
            httponly=True,
            samesite="strict",
        )
        return page

    @app.post(
        "/web/auth/register", response_class=HTMLResponse, include_in_schema=False
    )
    async def validate_registration(request: Request):
        # Count all attempts before parsing bodies or checking submitted fields.
        limited = limited_response(request, submit_limit)
        if limited is not None:
            return limited
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin not in {None, "null"}
            and origin != f"{request.url.scheme}://{request.url.netloc}"
        ):
            return security_retry()
        csrf = browser_context(request)
        if csrf is None:
            return security_retry()
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            return form_error(csrf)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 8192:
                return form_error(csrf)
            body.extend(chunk)
        try:
            fields = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=4,
            )
        except (ValueError, UnicodeError):
            return form_error(csrf)
        if not set(fields) <= {"name", "email", "password", "csrf"} or any(
            len(values) != 1 for values in fields.values()
        ):
            return form_error(csrf)
        submitted_csrf = fields.get("csrf", [""])[0]
        if _TOKEN.fullmatch(submitted_csrf) is None or not hmac.compare_digest(
            csrf, submitted_csrf
        ):
            return security_retry()
        checked = validate_registration_fields(
            fields.get("name", [""])[0],
            fields.get("email", [""])[0],
            fields.get("password", [""])[0],
        )
        if checked["errors"]:
            return form_response(
                csrf, fields=checked, errors=checked["errors"], code=400
            )
        return HTMLResponse(
            render_registration_waiting_page(checked["email"]), headers=_HEADERS
        )
