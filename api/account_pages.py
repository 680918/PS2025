"""Login, private welcome and logout for the isolated account application."""

import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from string import Template
from threading import BoundedSemaphore
from time import time
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from api.public_pages import _render_layout
from security.login_sessions import (
    SESSION_LIFETIME,
    sign_in,
    sign_out,
    signed_in_account,
)
from security.passwords import hash_password
from security.registration_rate_limit import RegistrationRateLimiter
from security.registration_validation import masked_registration_email


SESSION_COOKIE = "coach_login_session"
_FORM_COOKIE = "coach_login_form"
_FORM_LIFETIME = 1800
_TEMPLATES = Path(__file__).parent / "templates/public"
_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
}


def _login_html(*, csrf="", error="", email=""):
    body = Template(
        (_TEMPLATES / "account_login.html").read_text(encoding="utf-8")
    ).substitute(
        csrf=escape(csrf, quote=True),
        email=escape(email, quote=True),
        error=f'<div class="form-error-summary" role="alert">{escape(error)}</div>'
        if error
        else "",
    )
    return _render_layout("登录 · 知行成长教练", body, "login")


def _cookie(response, name, value, request, *, max_age):
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path="/web",
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
    )


def _clear(response, name, request):
    response.delete_cookie(
        name,
        path="/web",
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="strict",
    )


def register_account_pages(app, repository):
    key = secrets.token_bytes(32)
    # Do comparable Argon2 work for unknown addresses and legacy empty credentials.
    dummy_hash = hash_password(secrets.token_urlsafe(32))
    slots = BoundedSemaphore(2)
    submit_limit = RegistrationRateLimiter(per_client_limit=5, total_limit=50)
    view_limit = RegistrationRateLimiter(per_client_limit=60, total_limit=600)

    def signature(purpose, value):
        return hmac.new(
            key, f"{purpose}.{value}".encode("ascii"), hashlib.sha256
        ).hexdigest()

    def context(request):
        value = request.cookies.get(_FORM_COOKIE, "")
        if re.fullmatch(r"[A-Za-z0-9_-]{43}\.[0-9]{10}\.[0-9a-f]{64}", value) is None:
            return None
        nonce, expiry, signed = value.split(".")
        now = int(time())
        if now < int(expiry) <= now + _FORM_LIFETIME and hmac.compare_digest(
            signature("login-form", f"{nonce}.{expiry}"), signed
        ):
            return nonce
        return None

    def response(csrf="", *, error="", code=200, retry=0, email=""):
        headers = dict(_HEADERS)
        if retry:
            headers["Retry-After"] = str(retry)
        return HTMLResponse(
            _login_html(csrf=csrf, error=error, email=email),
            status_code=code,
            headers=headers,
        )

    def redirect(path):
        return RedirectResponse(path, status_code=303, headers=_HEADERS)

    def limited(request, limiter):
        wait = limiter.admit(request.client.host if request.client else "unknown")
        return (
            response(
                error=f"操作较频繁，请在 {wait} 秒后重新打开登录页。",
                code=429,
                retry=wait,
            )
            if wait
            else None
        )

    def same_origin(request):
        origin = request.headers.get("origin")
        return request.headers.get("sec-fetch-site") != "cross-site" and (
            origin in {None, "null"}
            or origin == f"{request.url.scheme}://{request.url.netloc}"
        )

    async def fields(request, expected):
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            return None
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 4096:
                return None
            body.extend(chunk)
        try:
            values = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=len(expected),
            )
        except (UnicodeError, ValueError):
            return None
        if set(values) != expected or any(len(value) != 1 for value in values.values()):
            return None
        return {name: value[0] for name, value in values.items()}

    def perform_login(email, password, previous):
        if not slots.acquire(blocking=False):
            return False
        try:
            return sign_in(
                repository,
                email,
                password,
                dummy_hash=dummy_hash,
                previous_token=previous,
            )
        finally:
            slots.release()

    @app.get("/web/login", response_class=HTMLResponse, include_in_schema=False)
    def login_page(request: Request):
        denied = limited(request, view_limit)
        if denied is not None:
            return denied
        try:
            account = signed_in_account(repository, request.cookies.get(SESSION_COOKIE))
        except sqlite3.Error:
            return response(error="服务暂时无法读取登录状态，请稍后重试。", code=503)
        if account is not None:
            return redirect("/web/welcome")
        csrf = context(request)
        page = response(csrf or "")
        if csrf is None:
            csrf = secrets.token_urlsafe(32)
            expiry = str(int(time()) + _FORM_LIFETIME)
            page = response(csrf)
            _cookie(
                page,
                _FORM_COOKIE,
                f"{csrf}.{expiry}.{signature('login-form', f'{csrf}.{expiry}')}",
                request,
                max_age=_FORM_LIFETIME,
            )
        if request.cookies.get(SESSION_COOKIE):
            _clear(page, SESSION_COOKIE, request)
        return page

    @app.post("/web/auth/login", response_class=HTMLResponse, include_in_schema=False)
    async def login(request: Request):
        denied = limited(request, submit_limit)
        if denied is not None:
            return denied
        csrf = context(request)
        if not same_origin(request) or csrf is None:
            return response(error="页面已过期或无法核对，请重新打开登录页。", code=403)
        values = await fields(request, {"email", "password", "csrf"})
        if values is None:
            return response(csrf, error="填写内容无法读取，请重新填写。", code=400)
        if not re.fullmatch(
            r"[A-Za-z0-9_-]{43}", values["csrf"]
        ) or not hmac.compare_digest(csrf, values["csrf"]):
            return response(error="页面已过期或无法核对，请重新打开登录页。", code=403)
        try:
            receipt = await run_in_threadpool(
                perform_login,
                values["email"],
                values["password"],
                request.cookies.get(SESSION_COOKIE),
            )
        except ValueError:
            receipt = None
        except sqlite3.Error:
            return response(csrf, error="服务暂时无法完成登录，请稍后再试。", code=503)
        if receipt is False:
            return response(csrf, error="服务暂时较忙，请稍后再试。", code=503, retry=2)
        if receipt is None:
            return response(
                csrf, error="邮箱或密码不正确，或邮箱尚未完成验证。", code=401
            )
        page = redirect("/web/welcome")
        remaining = min(
            SESSION_LIFETIME,
            max(
                1,
                int(receipt.expires_at.timestamp())
                - int(datetime.now(timezone.utc).timestamp()),
            ),
        )
        _cookie(page, SESSION_COOKIE, receipt.token, request, max_age=remaining)
        _clear(page, _FORM_COOKIE, request)
        return page

    @app.get("/web/welcome", response_class=HTMLResponse, include_in_schema=False)
    def welcome(request: Request):
        denied = limited(request, view_limit)
        if denied is not None:
            return denied
        token = request.cookies.get(SESSION_COOKIE)
        try:
            account = signed_in_account(repository, token)
        except sqlite3.Error:
            return response(error="服务暂时无法读取登录状态，请稍后重试。", code=503)
        if account is None:
            page = redirect("/web/login")
            _clear(page, SESSION_COOKIE, request)
            return page
        body = Template(
            (_TEMPLATES / "account_welcome.html").read_text(encoding="utf-8")
        ).substitute(
            name=escape(account.name),
            email=escape(masked_registration_email(account.email)),
            csrf=signature("logout", token),
        )
        return HTMLResponse(
            _render_layout("我的成长空间 · 知行", body, signed_in=True),
            headers=_HEADERS,
        )

    @app.post("/web/auth/logout", response_class=HTMLResponse, include_in_schema=False)
    async def logout(request: Request):
        if not same_origin(request):
            return response(error="操作无法核对，请返回成长空间后再退出。", code=403)
        token = request.cookies.get(SESSION_COOKIE)
        try:
            account = await run_in_threadpool(signed_in_account, repository, token)
        except sqlite3.Error:
            return response(error="服务暂时无法完成退出，请稍后重试。", code=503)
        if account is not None:
            values = await fields(request, {"csrf"})
            if (
                values is None
                or not re.fullmatch(r"[0-9a-f]{64}", values["csrf"])
                or not hmac.compare_digest(signature("logout", token), values["csrf"])
            ):
                return response(
                    error="操作无法核对，请返回成长空间后再退出。", code=403
                )
            try:
                await run_in_threadpool(sign_out, repository, token)
            except sqlite3.Error:
                return response(error="服务暂时无法完成退出，请稍后重试。", code=503)
        page = redirect("/web/login")
        _clear(page, SESSION_COOKIE, request)
        return page
