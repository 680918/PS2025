"""Protected registration applications and explicitly configured mail actions."""

import hashlib
import hmac
import re
import secrets
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import BoundedSemaphore
from time import time
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from api.public_pages import (
    render_registration_page,
    render_registration_problem_page,
    render_registration_rate_limited_page,
    render_registration_security_retry_page,
    render_registration_waiting_page,
    render_registration_mail_problem_page,
)
from security.email_verification import _trusted_activation_url
from security.registration_delivery import (
    get_registration_delivery_status,
    send_registration_verification,
)
from security.verification_mailer import SMTPSettings, MailConfigurationError
from security.registration_validation import validate_registration_fields
from security.registration_rate_limit import RegistrationRateLimiter
from security.pending_registration import (
    PendingRegistrationUnavailable,
    begin_browser_registration,
    get_browser_registration_status,
)


_COOKIE = "coach_registration_form"
_COOKIE_PATH = "/web"
_APPLICATION_COOKIE = "coach_registration_application"
_PENDING_PATH = "/web/register/pending"
_FORM_LIFETIME = 1800
_MAIL_FORM_LIFETIME = 600
_MAIL_PATH = "/web/register/send-verification"
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


@dataclass(frozen=True)
class RegistrationMailConfig:
    """Trusted server composition only. Never built from form data or Host headers.

    Simulation must inject its own sender and use a disposable test database.
    Normal startup leaves this configuration absent and cannot send mail.
    """

    activation_url: str = field(repr=False)
    settings: SMTPSettings = field(repr=False)
    simulated: bool = False
    sender: Callable | None = field(default=None, repr=False)

    def __post_init__(self):
        _trusted_activation_url(self.activation_url)
        if (
            not isinstance(self.settings, SMTPSettings)
            or type(self.simulated) is not bool
        ):
            raise MailConfigurationError("邮件发送配置无效。")
        if (self.simulated and not callable(self.sender)) or (
            not self.simulated and self.sender is not None
        ):
            raise MailConfigurationError("模拟发送需要单独的模拟发信器。")


def register_registration_pages(app, repository, *, mail_config=None):
    if mail_config is not None and not isinstance(mail_config, RegistrationMailConfig):
        raise MailConfigurationError("邮件发送配置无效。")
    # Single-process local development. Restarting requires reopening the form.
    signing_key = secrets.token_bytes(32)
    hash_slots = BoundedSemaphore(2)
    mail_slots = BoundedSemaphore(2)
    mail_limit = RegistrationRateLimiter(per_client_limit=3, total_limit=30)
    page_limit = RegistrationRateLimiter(
        per_client_limit=_GET_PER_CLIENT, total_limit=_GET_TOTAL
    )
    pending_limit = RegistrationRateLimiter(
        per_client_limit=_GET_PER_CLIENT, total_limit=_GET_TOTAL
    )
    submit_limit = RegistrationRateLimiter(
        per_client_limit=_POST_PER_CLIENT, total_limit=_POST_TOTAL
    )

    def limited_response(request, limiter, *, mail=False):
        # Use the transport peer, never arbitrary Forwarded/X-Forwarded-For
        # headers or a resettable browser cookie. Local runner disables proxies.
        client_key = request.client.host if request.client else "unknown"
        wait = limiter.admit(client_key)
        if wait:
            return HTMLResponse(
                render_registration_mail_problem_page("limited", wait_seconds=wait)
                if mail
                else render_registration_rate_limited_page(wait),
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

    def problem(kind, code, *, retry_after=None):
        headers = dict(_HEADERS)
        if retry_after is not None:
            headers["Retry-After"] = str(retry_after)
        return HTMLResponse(
            render_registration_problem_page(kind), status_code=code, headers=headers
        )

    def application_credentials(request):
        value = request.cookies.get(_APPLICATION_COOKIE, "")
        if len(value) != 89 or value.count(".") != 1:
            return None
        request_id, secret = value.split(".")
        if (
            re.fullmatch(r"registration_[0-9a-f]{32}", request_id) is None
            or _TOKEN.fullmatch(secret) is None
        ):
            return None
        return request_id, secret

    def application_status(request):
        credentials = application_credentials(request)
        return (
            get_browser_registration_status(repository, *credentials)
            if credentials
            else None
        )

    def pending_data(request):
        credentials = application_credentials(request)
        if credentials is None:
            return None
        status = get_browser_registration_status(repository, *credentials)
        if status is None:
            return None
        delivery = get_registration_delivery_status(repository, *credentials)
        if delivery is None:
            return None
        return status, delivery, credentials

    def mail_signature(credentials, action, expires):
        # Bind the operation to this application and its HttpOnly owner cookie.
        payload = f"registration-mail.{credentials[0]}.{credentials[1]}.{action}.{expires}".encode(
            "ascii"
        )
        return hmac.new(signing_key, payload, hashlib.sha256).hexdigest()

    def mail_token(credentials, status, action):
        expires = str(
            min(int(time()) + _MAIL_FORM_LIFETIME, int(status.expires_at.timestamp()))
        )
        return f"{expires}.{mail_signature(credentials, action, expires)}"

    def valid_mail_token(credentials, action, value):
        if (
            not isinstance(value, str)
            or re.fullmatch(r"[0-9]{10}\.[0-9a-f]{64}", value) is None
        ):
            return False
        expires, signed = value.split(".")
        now = int(time())
        return now < int(expires) <= now + _MAIL_FORM_LIFETIME and hmac.compare_digest(
            mail_signature(credentials, action, expires), signed
        )

    def mail_problem(kind, code, *, wait=0):
        headers = dict(_HEADERS)
        if wait:
            headers["Retry-After"] = str(wait)
        return HTMLResponse(
            render_registration_mail_problem_page(kind, wait_seconds=wait),
            status_code=code,
            headers=headers,
        )

    def perform_delivery(credentials, action):
        if not mail_slots.acquire(blocking=False):
            return False
        try:
            send_registration_verification(
                repository,
                credentials[0],
                mail_config.activation_url,
                mail_config.settings,
                browser_secret=credentials[1],
                retry_failed=action == "retry",
                sender=mail_config.sender,
            )
            return True
        finally:
            mail_slots.release()

    def save_application(fields, password):
        # Never queue an unbounded number of memory-intensive password hashes.
        if not hash_slots.acquire(blocking=False):
            return None
        try:
            return begin_browser_registration(
                repository,
                email=fields["email"],
                name=fields["name"],
                password=password,
            )
        finally:
            hash_slots.release()

    def pending_redirect():
        return RedirectResponse(_PENDING_PATH, status_code=303, headers=_HEADERS)

    @app.get(_PENDING_PATH, response_class=HTMLResponse, include_in_schema=False)
    def pending_page(request: Request):
        limited = limited_response(request, pending_limit)
        if limited is not None:
            return limited
        try:
            data = pending_data(request)
        except sqlite3.Error:
            if mail_config is not None:
                return mail_problem("unavailable", 503)
            return problem("unavailable", 503)
        if data is None:
            page = problem("missing", 403)
            page.delete_cookie(
                _APPLICATION_COOKIE,
                path=_COOKIE_PATH,
                secure=request.url.scheme == "https",
                httponly=True,
                samesite="strict",
            )
            return page
        status, delivery, credentials = data
        action = "retry" if delivery.state == "failed" else "send"
        return HTMLResponse(
            render_registration_waiting_page(
                status.masked_email,
                status.expires_at,
                delivery_state=delivery.state,
                retry_after_seconds=delivery.retry_after_seconds,
                mail_enabled=mail_config is not None,
                simulated=mail_config.simulated if mail_config is not None else False,
                csrf=mail_token(credentials, status, action)
                if mail_config is not None
                else "",
            ),
            headers=_HEADERS,
        )

    @app.post(_MAIL_PATH, response_class=HTMLResponse, include_in_schema=False)
    async def send_registration_mail(request: Request):
        limited = limited_response(request, mail_limit, mail=True)
        if limited is not None:
            return limited
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin not in {None, "null"}
            and origin != f"{request.url.scheme}://{request.url.netloc}"
        ):
            return mail_problem("security", 403)
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            return mail_problem("security", 400)
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 2048:
                return mail_problem("security", 400)
            body.extend(chunk)
        try:
            fields = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=2,
            )
        except (ValueError, UnicodeError):
            return mail_problem("security", 400)
        if set(fields) != {"csrf", "action"} or any(
            len(values) != 1 for values in fields.values()
        ):
            return mail_problem("security", 400)
        action = fields["action"][0]
        if action not in {"send", "retry"}:
            return mail_problem("security", 400)
        try:
            data = await run_in_threadpool(pending_data, request)
        except sqlite3.Error:
            return mail_problem("unavailable", 503)
        if data is None:
            return mail_problem("security", 403)
        _, _, credentials = data
        if not valid_mail_token(credentials, action, fields["csrf"][0]):
            return mail_problem("security", 403)
        if mail_config is None:
            return mail_problem("disabled", 503)
        try:
            completed = await run_in_threadpool(perform_delivery, credentials, action)
        except ValueError:
            # A stale form, concurrent claim, or cooldown cannot trigger resend.
            return pending_redirect()
        except sqlite3.Error:
            return mail_problem("unavailable", 503)
        if not completed:
            return mail_problem("unavailable", 503, wait=2)
        # Refreshing the result never replays the POST or changes the token.
        return pending_redirect()

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
        try:
            # A repeat submission from the same browser cannot change an active
            # application's email/password or silently replace its ownership.
            active = await run_in_threadpool(application_status, request)
            if active is not None:
                return pending_redirect()
            receipt = await run_in_threadpool(
                save_application, checked, fields["password"][0]
            )
        except PendingRegistrationUnavailable:
            return problem("conflict", 409)
        except sqlite3.Error:
            return problem("unavailable", 503)
        if receipt is None:
            return problem("unavailable", 503, retry_after=2)
        page = pending_redirect()
        max_age = max(
            1,
            int(receipt.expires_at.timestamp())
            - int(datetime.now(timezone.utc).timestamp()),
        )
        page.set_cookie(
            _APPLICATION_COOKIE,
            f"{receipt.request_id}.{receipt.browser_secret}",
            max_age=max_age,
            path=_COOKIE_PATH,
            secure=request.url.scheme == "https",
            httponly=True,
            samesite="strict",
        )
        return page
