"""Email recovery pages; public responses never disclose account existence."""

import hashlib
import hmac
import re
import secrets
import sqlite3
from html import escape
from threading import BoundedSemaphore, Lock
from time import time
from urllib.parse import parse_qs, urlsplit, urlunsplit

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool

from api.account_pages import _HEADERS as ACCOUNT_HEADERS, _clear, _cookie
from api.public_pages import _render_layout
from security.password_reset import (
    RESET_LIFETIME,
    complete_password_reset,
    issue_password_reset,
    reset_available,
    reset_token_hash,
    send_password_reset_email,
    send_password_changed_email,
    PasswordChangedMessage,
)
from security.registration_rate_limit import RegistrationRateLimiter
from security.registration_validation import validate_registration_fields


REQUEST_COOKIE = "coach_recovery_form"
RESET_COOKIE = "coach_password_reset"
_TOKEN = r"[A-Za-z0-9_-]{43}"
_HEADERS = {
    **ACCOUNT_HEADERS,
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
}


def register_password_reset_pages(app, repository, *, mail_config=None):
    key = secrets.token_bytes(32)
    mail_slots = BoundedSemaphore(2)
    hash_slots = BoundedSemaphore(2)
    view_limit = RegistrationRateLimiter(per_client_limit=60, total_limit=600)
    send_limit = RegistrationRateLimiter(per_client_limit=3, total_limit=30)
    address_limit = RegistrationRateLimiter(per_client_limit=1, total_limit=30)
    reset_limit = RegistrationRateLimiter(per_client_limit=5, total_limit=50)
    preview = {}
    preview_lock = Lock()
    simulated = mail_config is not None and mail_config.simulated
    reset_url = None
    if mail_config is not None:
        configured = urlsplit(mail_config.activation_url)
        reset_url = urlunsplit(
            (configured.scheme, configured.netloc, "/web/reset-password", "", "")
        )

    def sign(purpose, value):
        return hmac.new(
            key, f"{purpose}.{value}".encode("ascii"), hashlib.sha256
        ).hexdigest()

    def make_cookie(purpose, *parts):
        payload = ".".join((*parts, str(int(time()) + RESET_LIFETIME)))
        return f"{payload}.{sign(purpose, payload)}"

    def context(request, purpose):
        cookie = request.cookies.get(
            REQUEST_COOKIE if purpose == "request" else RESET_COOKIE, ""
        )
        pattern = (
            rf"({_TOKEN})\.([0-9]{{10}})\.([0-9a-f]{{64}})"
            if purpose == "request"
            else rf"({_TOKEN})\.({_TOKEN})\.([0-9]{{10}})\.([0-9a-f]{{64}})"
        )
        match = re.fullmatch(pattern, cookie)
        if not match:
            return None
        parts = match.groups()
        payload, signed = cookie.rsplit(".", 1)
        if not int(time()) < int(parts[-2]) <= int(time()) + RESET_LIFETIME:
            return None
        return (
            parts[:-2] if hmac.compare_digest(sign(purpose, payload), signed) else None
        )

    def card(title, text, form="", *, notice="", status=200):
        alert = (
            f'<div class="form-error-summary" role="alert">{escape(notice)}</div>'
            if notice
            else ""
        )
        body = (
            '<main id="main-content" class="auth-layout recovery-layout">'
            '<section class="auth-story"><p class="eyebrow"><span class="small-line" aria-hidden="true"></span>BACK TO YOUR GROWTH</p>'
            '<h1>成长的积累，<br>一直为你保留。</h1><p class="auth-description">通过注册邮箱，重新回到自己的成长空间。</p>'
            '<ul class="story-list"><li>学习记录和知识资产继续保留</li><li>只有你确认新密码，旧密码才会改变</li><li>重置后，用新密码重新登录</li></ul></section>'
            f'<section class="auth-card"><span class="card-mark" aria-hidden="true">知</span><h2>{escape(title)}</h2>'
            f'<p class="auth-intro">{text}</p>{alert}{form}'
            '<p id="recovery-status" class="recovery-status" role="status" aria-live="polite" tabindex="-1"></p>'
            '<a class="back-link" href="/web/login">← 返回登录</a></section></main>'
            '<script src="/static/password-recovery.js" defer></script>'
        )
        return HTMLResponse(
            _render_layout(title + " · 知行", body),
            status_code=status,
            headers=_HEADERS,
        )

    def forgot_form(nonce):
        return (
            '<form method="post" action="/web/forgot-password" data-recovery-form data-wait="正在提交找回请求，请稍候…">'
            f'<input type="hidden" name="csrf" value="{nonce}">'
            '<fieldset><legend class="visually-hidden">注册邮箱找回</legend>'
            '<label for="recovery-email">注册邮箱</label><input id="recovery-email" name="email" type="email" autocomplete="username" maxlength="254" placeholder="注册时使用的邮箱" required>'
            '<button class="button button-primary button-full" type="submit">发送密码重置邮件 →</button></fieldset></form>'
            '<p class="availability-note">链接 30 分钟内有效，只能使用一次。重新发送至少间隔 60 秒。</p>'
        )

    def reset_form(nonce):
        return (
            '<form method="post" action="/web/reset-password" data-recovery-form data-wait="正在安全保存新密码，请稍候…">'
            f'<input type="hidden" name="csrf" value="{nonce}">'
            '<fieldset><legend class="visually-hidden">确认新密码</legend>'
            '<label for="new-password">新密码</label><input id="new-password" type="password" name="password" autocomplete="new-password" minlength="15" maxlength="128" aria-describedby="password-hint" required>'
            '<p id="password-hint" class="availability-note">15–128 个字符，可以用中文、空格或一段好记的话。</p>'
            '<label for="repeat-password">再次输入新密码</label><input id="repeat-password" type="password" name="confirmation" autocomplete="new-password" minlength="15" maxlength="128" required>'
            '<button class="button button-primary button-full" type="submit">确认设置新密码 →</button></fieldset></form>'
            '<p class="availability-note">确认后，之前所有登录状态都会失效。学习记录、教案和资料继续保留。</p>'
        )

    def problem(request, message, *, status=400, retry=0, nonce="", resetting=False):
        if "application/json" in request.headers.get("accept", ""):
            page = JSONResponse(
                {"error": message}, status_code=status, headers=_HEADERS
            )
        else:
            form = (
                (reset_form(nonce) if resetting else forgot_form(nonce))
                if nonce
                else '<p><a class="text-link" href="/web/forgot-password">重新申请重置邮件 →</a></p>'
            )
            page = card(
                "重新设置密码" if resetting else "找回密码",
                "请按下面提示继续。",
                form,
                notice=message,
                status=status,
            )
        if retry:
            page.headers["Retry-After"] = str(retry)
        return page

    def redirect(request, path):
        if "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"redirect": path}, headers=_HEADERS)
        return RedirectResponse(path, status_code=303, headers=_HEADERS)

    def limited(request, limiter):
        wait = limiter.admit(request.client.host if request.client else "unknown")
        return (
            problem(
                request, f"操作较频繁，请在 {wait} 秒后重试。", status=429, retry=wait
            )
            if wait
            else None
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

    def same_origin(request):
        return request.headers.get(
            "sec-fetch-site"
        ) != "cross-site" and request.headers.get("origin") in {
            None,
            f"{request.url.scheme}://{request.url.netloc}",
        }

    def dispatch(email, nonce):
        """Runs AFTER the generic response: mailbox existence and SMTP latency stay private.

        No durable queue or automatic retry. Persisted issuance enforces cooldown
        after restart. An interrupted delivery is explicitly treated as uncertain.
        """
        if not mail_slots.acquire(blocking=False):
            return
        try:
            if (
                mail_config.allowed_recipient is not None
                and email != mail_config.allowed_recipient
            ):
                return
            message = issue_password_reset(repository, email, reset_url)
            if message is None:
                return
            sender = mail_config.sender if simulated else send_password_reset_email
            sender(message, mail_config.settings)
            if simulated:
                with preview_lock:
                    current = int(time())
                    for old, item in list(preview.items()):
                        if item.expires_at.timestamp() <= current:
                            del preview[old]
                    if len(preview) < 120 or nonce in preview:
                        preview[nonce] = message
        except Exception:
            # Never log credentials, links, addresses or raw provider errors.
            # Keep the token usable in case the server accepted DATA before disconnect.
            pass
        finally:
            mail_slots.release()

    def notify(recipient):
        if mail_config is None or (
            mail_config.allowed_recipient is not None
            and recipient != mail_config.allowed_recipient
        ):
            return
        if not mail_slots.acquire(blocking=False):
            return
        try:
            message = PasswordChangedMessage(recipient)
            sender = mail_config.sender if simulated else send_password_changed_email
            sender(message, mail_config.settings)
        except Exception:
            pass  # The committed password must never be rolled back for mail failure.
        finally:
            mail_slots.release()

    @app.get(
        "/web/forgot-password", response_class=HTMLResponse, include_in_schema=False
    )
    def forgot(request: Request):
        denied = limited(request, view_limit)
        if denied is not None:
            return denied
        ctx = context(request, "request")
        nonce = ctx[0] if ctx else secrets.token_urlsafe(32)
        page = card(
            "找回密码",
            "填写注册邮箱，我们将通过邮件帮助你重新设置密码。",
            forgot_form(nonce),
        )
        if ctx is None:
            _cookie(
                page,
                REQUEST_COOKIE,
                make_cookie("request", nonce),
                request,
                max_age=RESET_LIFETIME,
            )
        return page

    @app.post("/web/forgot-password", include_in_schema=False)
    async def send(request: Request):
        denied = limited(request, send_limit)
        if denied is not None:
            return denied
        ctx = context(request, "request")
        if ctx is None or not same_origin(request):
            return problem(
                request, "页面已过期或无法核对，请重新打开找回密码页面。", status=403
            )
        values = await fields(request, {"csrf", "email"})
        if values is None:
            return problem(request, "填写内容无法读取，请重新填写。", nonce=ctx[0])
        if re.fullmatch(_TOKEN, values["csrf"]) is None or not hmac.compare_digest(
            ctx[0], values["csrf"]
        ):
            return problem(
                request, "页面已过期或无法核对，请重新打开找回密码页面。", status=403
            )
        checked = validate_registration_fields(
            "", values["email"], "a valid temporary phrase"
        )
        if "email" in checked["errors"]:
            return problem(request, checked["errors"]["email"], nonce=ctx[0])
        if mail_config is None:
            return problem(
                request,
                "邮件发送尚未启用，请由产品维护者在本机启动邮件服务后再试。",
                status=503,
                nonce=ctx[0],
            )
        email = checked["email"]
        wait = address_limit.admit(hashlib.sha256(email.encode("utf-8")).hexdigest())
        if wait:
            return problem(
                request,
                f"同一邮箱请间隔 {wait} 秒后再申请。",
                status=429,
                retry=wait,
                nonce=ctx[0],
            )
        page = redirect(request, "/web/forgot-password/submitted")
        page.background = BackgroundTask(dispatch, email, ctx[0])
        return page

    @app.get(
        "/web/forgot-password/submitted",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def submitted(request: Request):
        denied = limited(request, view_limit)
        if denied is not None:
            return denied
        demo = (
            '<p><a class="text-link" href="/web/trial-reset-mailbox">查看本浏览器的模拟重置邮件 →</a></p>'
            if simulated
            else ""
        )
        return card(
            "请查收重置邮件",
            "请求已提交。若邮箱已注册并完成验证，且邮件投递成功，你会收到设置新密码的链接。",
            demo
            + '<p class="availability-note">邮件可能稍有延迟，请检查收件箱和垃圾邮件。链接 30 分钟内有效，请使用最新邮件。</p><details class="account-help"><summary>没有收到邮件？</summary><p>请确认使用注册邮箱且已完成验证；也可能是邮件服务未能投递。请稍后再查收，至少间隔 60 秒后主动重试。重复发送会使旧链接失效。服务若中断，不会自动补发。</p></details><p><a class="text-link" href="/web/forgot-password">检查邮箱并重新申请 →</a></p>',
        )

    @app.get(
        "/web/reset-password", response_class=HTMLResponse, include_in_schema=False
    )
    def reset_page(request: Request):
        denied = limited(request, view_limit)
        if denied is not None:
            return denied
        query = request.query_params
        if query:
            token = query.get("token", "")
            if (
                len(query) != 1
                or len(query.getlist("token")) != 1
                or reset_token_hash(token) is None
            ):
                return problem(
                    request, "链接无效，请重新申请密码重置邮件。", resetting=True
                )
            try:
                available = reset_available(repository, token)
            except sqlite3.Error:
                return problem(
                    request,
                    "暂时无法读取重置请求，请稍后重新打开邮件链接。",
                    status=503,
                    resetting=True,
                )
            if not available:
                return problem(
                    request,
                    "链接已过期、已使用或已被新邮件替换，请重新申请。",
                    resetting=True,
                )
            page = RedirectResponse(
                "/web/reset-password", status_code=303, headers=_HEADERS
            )
            # Mail links start a cross-site top-level GET. Strict would omit this
            # newly set context on the clean-URL redirect. Only this short-lived,
            # signed reset context uses Lax; password changes still require a
            # same-origin POST and its browser-bound CSRF nonce.
            page.set_cookie(
                RESET_COOKIE,
                make_cookie("reset", token, secrets.token_urlsafe(32)),
                max_age=RESET_LIFETIME,
                path="/web",
                httponly=True,
                secure=request.url.scheme == "https",
                samesite="lax",
            )
            return page
        ctx = context(request, "reset")
        try:
            available = ctx is not None and reset_available(repository, ctx[0])
        except sqlite3.Error:
            return problem(
                request,
                "暂时无法读取重置请求，请稍后重新打开邮件链接。",
                status=503,
                resetting=True,
            )
        if not available:
            return problem(
                request,
                "请从最新的重置邮件打开链接；页面过期时可重新申请。",
                resetting=True,
            )
        return card(
            "设置新密码",
            "邮件链接已确认本次重置账户，无需再次填写邮箱。请填写两次新密码。",
            reset_form(ctx[1]),
        )

    @app.post("/web/reset-password", include_in_schema=False)
    async def reset(request: Request):
        denied = limited(request, reset_limit)
        if denied is not None:
            return denied
        ctx = context(request, "reset")
        if ctx is None or not same_origin(request):
            return problem(
                request,
                "页面已过期或无法核对，请从最新邮件重新打开链接。",
                status=403,
                resetting=True,
            )
        values = await fields(request, {"csrf", "password", "confirmation"})
        if values is None:
            return problem(
                request, "填写内容无法读取，请重新填写。", nonce=ctx[1], resetting=True
            )
        if re.fullmatch(_TOKEN, values["csrf"]) is None or not hmac.compare_digest(
            ctx[1], values["csrf"]
        ):
            return problem(
                request,
                "页面已过期或无法核对，请从最新邮件重新打开链接。",
                status=403,
                resetting=True,
            )
        error = validate_registration_fields(
            "", "check@example.com", values["password"]
        )["errors"].get("password")
        if error is None and values["password"] != values["confirmation"]:
            error = "两次输入的新密码不一致，请重新填写。"
        if error:
            return problem(request, error, nonce=ctx[1], resetting=True)
        if not hash_slots.acquire(blocking=False):
            return problem(
                request,
                "服务暂时较忙，请稍后再次确认。",
                status=503,
                retry=2,
                nonce=ctx[1],
                resetting=True,
            )
        try:
            recipient = await run_in_threadpool(
                complete_password_reset, repository, ctx[0], values["password"]
            )
        except (sqlite3.Error, ValueError):
            return problem(
                request,
                "暂时无法保存新密码，请稍后重试。",
                status=503,
                nonce=ctx[1],
                resetting=True,
            )
        finally:
            hash_slots.release()
        if not recipient:
            return problem(
                request,
                "链接已过期、已使用或已被新邮件替换，请重新申请。",
                resetting=True,
            )
        page = redirect(request, "/web/password-reset-complete")
        for cookie in (RESET_COOKIE, REQUEST_COOKIE, "coach_login_session"):
            _clear(page, cookie, request)
        page.background = BackgroundTask(notify, recipient)
        return page

    @app.get(
        "/web/password-reset-complete",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def complete(request: Request):
        denied = limited(request, view_limit)
        if denied is not None:
            return denied
        return card(
            "新密码已设置",
            "之前的登录状态已失效，请用新密码重新登录。",
            '<p>学习记录、教案和资料都为你保留。</p><a class="button button-primary button-full" href="/web/login">用新密码登录 →</a>',
        )

    if simulated:

        @app.get(
            "/web/trial-reset-mailbox",
            response_class=HTMLResponse,
            include_in_schema=False,
        )
        def mailbox(request: Request):
            denied = limited(request, view_limit)
            if denied is not None:
                return denied
            ctx = context(request, "request")
            with preview_lock:
                message = preview.get(ctx[0]) if ctx else None
            link = "<p>当前没有可查看的模拟重置邮件。请使用已完成验证的虚构账户申请，稍后刷新本页。</p>"
            if message and message.expires_at.timestamp() > time():
                link = f'<a class="button button-primary button-full" href="{escape(message.activation_url, quote=True)}">打开模拟重置邮件 →</a>'
            return card(
                "模拟重置收件箱",
                "本机模拟，不发送真实邮件。仅显示当前浏览器主动申请的重置链接。",
                link,
            )
