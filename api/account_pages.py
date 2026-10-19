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
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from api.coach_markdown import coach_markdown
from api.memory_pages import register_memory_pages
from api.study_pages import register_study_pages
from api.conversation_pages import register_conversation_pages
from api.usage_pages import register_usage_pages
from api.growth_pages import register_growth_pages
from coach.ai_usage import usage_message
from coach.book_study import study_directory
from coach.learning_topics import discussion_material, discussion_part
from api.public_pages import _render_layout
from api.library_pages import register_library_pages, library_csrf
from api.booklet_pages import register_booklet_pages
from coach.dialogue import send_dialogue
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
_DIALOGUE_HEADERS = {
    **_HEADERS,
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
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


def register_account_pages(
    app,
    repository,
    *,
    dialogue_repository=None,
    dialogue_responder=None,
    dialogue_label="",
    materials_repository=None,
):
    key = secrets.token_bytes(32)
    # Do comparable Argon2 work for unknown addresses and legacy empty credentials.
    dummy_hash = hash_password(secrets.token_urlsafe(32))
    slots = BoundedSemaphore(2)
    submit_limit = RegistrationRateLimiter(per_client_limit=5, total_limit=50)
    view_limit = RegistrationRateLimiter(per_client_limit=60, total_limit=600)
    dialogue_limit = RegistrationRateLimiter(per_client_limit=8, total_limit=80)
    history_limit = RegistrationRateLimiter(per_client_limit=30, total_limit=300)
    dialogue_slots = BoundedSemaphore(2)
    if materials_repository is not None:
        register_library_pages(
            app,
            repository,
            materials_repository,
            dialogue_repository,
            csrf_key=key,
            summary_responder=dialogue_responder,
            summary_slots=dialogue_slots,
            summary_limit=dialogue_limit,
        )

    if dialogue_repository is not None:
        register_usage_pages(app, repository, dialogue_repository)
        register_growth_pages(app, repository, dialogue_repository)
        register_conversation_pages(app, repository, dialogue_repository, csrf_key=key)
        register_booklet_pages(app, repository, dialogue_repository, csrf_key=key)
        register_memory_pages(app, repository, dialogue_repository, csrf_key=key)
        register_study_pages(
            app,
            repository,
            dialogue_repository,
            materials_repository,
            csrf_key=key,
            enabled=dialogue_responder is not None,
            resume=lambda uid, identity, nonce: perform_dialogue(
                uid, "", nonce, "continue", study_id=identity
            ),
        )

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

    async def fields(request, expected, *, max_bytes=4096, optional=frozenset()):
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            return None
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > max_bytes:
                return None
            body.extend(chunk)
        try:
            values = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=len(expected) + len(optional),
            )
        except (UnicodeError, ValueError):
            return None
        if not expected <= set(values) <= expected | optional or any(
            len(value) != 1 for value in values.values()
        ):
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
        try:
            view = (
                dialogue_repository.view(account.user_id)
                if dialogue_repository
                else {"turns": [], "learning": None}
            )
            dialogue_body, learning_panel, assets_panel = workspace(
                view, token, account.user_id
            )
        except sqlite3.Error:
            return dialogue_problem("暂时无法读取对话记录，请稍后再试。", 503)
        body = Template(
            (_TEMPLATES / "account_welcome.html").read_text(encoding="utf-8")
        ).substitute(
            name=escape(account.name),
            email=escape(masked_registration_email(account.email)),
            csrf=signature("logout", token),
            dialogue_body=dialogue_body,
            learning_panel=learning_panel,
            assets_panel=assets_panel,
        )
        return HTMLResponse(
            _render_layout("我的成长空间 · 知行", body, signed_in=True),
            headers=_DIALOGUE_HEADERS,
        )

    @app.get("/web/coach/history", include_in_schema=False)
    def history_page(request: Request):
        def problem(text, status):
            return JSONResponse({"error": text}, status_code=status, headers=_HEADERS)

        if not same_origin(request):
            return problem("无法核对请求来源。", 403)
        try:
            account = signed_in_account(repository, request.cookies.get(SESSION_COOKIE))
        except sqlite3.Error:
            return problem("暂时无法读取登录状态。", 503)
        if account is None:
            return problem("登录已过期，请重新登录。", 401)
        parameters = request.query_params
        before = parameters.get("before", "")
        if (
            len(parameters.multi_items()) != 1
            or set(parameters) != {"before"}
            or re.fullmatch(r"[1-9][0-9]{0,18}", before) is None
            or int(before) > 9223372036854775807
        ):
            return problem("无法读取历史位置。", 400)
        wait = history_limit.admit(request.client.host if request.client else "unknown")
        if wait:
            page = problem("加载较频繁，请稍后重试。", 429)
            page.headers["Retry-After"] = str(wait)
            return page
        try:
            page = dialogue_repository.history_page(account.user_id, before=int(before))
        except sqlite3.Error:
            return problem("暂时无法读取历史对话。", 503)
        for turn in page["turns"]:
            if turn["status"] == "complete":
                turn["assistant_html"] = coach_markdown(turn["assistant_content"])
        return JSONResponse(page, headers=_HEADERS)

    def dialogue_form(token, action, content, study_id="", part_id=None):
        nonce = secrets.token_urlsafe(32)
        payload = f"{token}.{nonce}.{action}" + (f".{study_id}" if study_id else "")
        if part_id is not None:
            payload += ".part:" + part_id
            content = (
                f'<input type="hidden" name="part_id" value="{part_id}">' + content
            )
        csrf = signature("dialogue", payload)
        if study_id:
            content = (
                f'<input type="hidden" name="study_id" value="{study_id}">' + content
            )
        return f'<form method="post" action="/web/coach/message"><input type="hidden" name="nonce" value="{nonce}"><input type="hidden" name="csrf" value="{csrf}"><input type="hidden" name="action" value="{action}">{content}</form>'

    def workspace(view, token, user_id):
        enabled = dialogue_responder is not None
        active_topic = dialogue_repository.active_topic(user_id)
        study_id = active_topic["topic_id"] if active_topic else ""
        part = discussion_part(dialogue_repository, materials_repository, user_id)
        stored_part = dialogue_repository.topic_part(user_id)
        form_part = (
            (stored_part["chunk_id"] if stored_part else "") if study_id else None
        )
        pending = any(turn["status"] == "pending" for turn in view["turns"])
        history = []
        for index, turn in enumerate(view["turns"]):
            latest = ' id="latest-reply"' if index == len(view["turns"]) - 1 else ""
            history.append(
                f'<article class="dialogue-message dialogue-user"><p class="message-author">你</p><div class="message-content">{escape(turn["user_content"])}</div></article>'
            )
            if turn["status"] == "complete":
                citations_html = "".join(
                    '<details class="citation"><summary>引用依据：'
                    + escape(source["title"] + " · " + source["locator"])
                    + "</summary><p>"
                    + escape(source["excerpt"])
                    + "</p></details>"
                    for source in turn.get("citations", [])
                )
                history.append(
                    f'<article{latest} class="dialogue-message dialogue-coach"><p class="message-author">知行 · 成长教练</p><div class="message-content markdown-content">{coach_markdown(turn["assistant_content"])}</div>{citations_html}</article>'
                )
            elif turn["status"] == "pending":
                history.append(
                    f'<p{latest} class="dialogue-state" role="status"><span class="waiting-dots" aria-hidden="true"><i></i><i></i><i></i></span>教练正在回复。请稍后刷新查看，刷新不会重复发送。</p>'
                )
            else:
                history.append(
                    f'<p{latest} class="dialogue-state" role="status">这次未能取得回复。你的消息已保留；需要时可以重新输入发送。系统不会自动重试。</p>'
                )
        disabled = "" if enabled and not pending else " disabled"
        composer = f'<div class="conversation-composer" aria-label="统一对话输入区"><label class="visually-hidden" for="coach-message">发送给成长教练的消息</label><textarea id="coach-message" name="message" rows="2" maxlength="2000" required placeholder="说说你的想法，或围绕所选资料提问…" aria-describedby="conversation-availability"{disabled}></textarea><div class="conversation-tools"><a class="button button-outline" href="/web/materials#add-material">＋ 添加资料</a><button class="button button-primary" type="submit"{disabled}>发送</button></div></div>'
        if enabled:
            composer = dialogue_form(token, "message", composer, study_id, form_part)
        learning = view["learning"]
        selected = discussion_material(
            dialogue_repository, materials_repository, user_id
        )
        draft_items = dialogue_repository.list_knowledge(
            user_id, status="pending", limit=1
        )
        review = dialogue_repository.review(user_id)
        mobile_context = (
            '<div class="mobile-learning-context" aria-label="学习位置速览"><p>当前学习主题 · <strong>'
            + escape(learning["topic"] if learning else "尚未开始")
            + '</strong></p><p class="mobile-learning-progress">学习进度 · '
            + escape(learning["progress"] if learning else "尚无学习记录")
            + "</p><p>讨论资料 · "
            + escape(
                (selected["title"] + (" · " + part["locator"] if part else ""))
                if selected
                else "未关联资料"
            )
            + '</p><a class="text-link" href="#learning-title">查看学习详情与续学 →</a></div>'
        )
        body = (
            mobile_context
            + f'<div id="dialogue-history" class="dialogue-history" role="region" aria-label="聊天记录" tabindex="0"><div class="history-loader"><button id="history-load" class="history-load" type="button" data-before="{view.get("before") or ""}"{"" if view.get("before") else " hidden"}>加载更早的对话</button><p id="history-load-status" role="status"></p></div><div id="dialogue-messages">'
            + "".join(history)
            + '</div></div><div id="conversation-input">'
            + composer
            + '</div><script src="/static/coach-dialogue.js" defer></script>'
        )
        if learning:
            details = f'<h3>{escape(learning["topic"])}</h3><dl><dt>学习进度 · 已讨论</dt><dd>{escape(learning["progress"])}</dd><dt>下一步</dt><dd>{escape(learning["next_step"])}</dd></dl><p class="learning-record-note">记录会随讨论更新，也可自行修正；不代表已经掌握。</p>'
            if study_id:
                details += f'<a class="text-link study-directory-link" href="/web/studies/{study_id}/edit">修改学习记录</a>'
        else:
            details = "<h3>还没有开始主题学习</h3><p>在对话中说“我想学习……”即可开始。教练会在讨论后整理学习位置。</p><dl><dt>学习进度</dt><dd>尚无学习记录</dd><dt>下一步</dt><dd>选择一个你想了解的主题。</dd></dl>"
        button = f'<button class="button button-primary button-full" type="submit"{"" if learning and enabled and not pending else " disabled"}>继续上次学习</button>'
        if enabled and learning:
            button = dialogue_form(
                token,
                "continue",
                '<input type="hidden" name="message" value="">' + button,
                study_id,
                form_part,
            )
        else:
            button = button.replace('type="submit"', 'type="button"')
        lesson_button = (
            dialogue_form(
                token,
                "lesson",
                '<input type="hidden" name="message" value=""><button class="button button-outline button-full" type="submit">把本次知识点整理成教案</button>',
                study_id,
                form_part,
            )
            if enabled and not pending and (view["turns"] or selected)
            else ""
        )
        study_action = ""
        source_content = '<p class="source-empty">未关联资料</p><a class="text-link" href="/web/materials">添加或选择资料 →</a>'
        if selected:
            source_content = (
                '<p><a class="text-link" href="/web/materials/'
                + selected["material_id"]
                + '">'
                + escape(selected["title"])
                + '</a></p><p>已选入讨论；回答将根据相关片段整理。</p><form method="post" action="/web/materials/clear"><input type="hidden" name="csrf" value="'
                + library_csrf(key, token, "clear")
                + '"><button class="history-load" type="submit">取消当前资料</button></form>'
            )
        if part and selected:
            summary = (
                '<p class="study-position-summary">本次资料 · '
                + escape(selected["title"])
                + "<br>"
                + escape(part["locator"])
                + "</p>"
            )
            source_content += (
                '<div class="selected-study-part"><p><strong>当前选段 · '
                + escape(part["locator"])
                + '</strong></p><p>本轮只以这一段为资料依据；尚不代表已学完。</p><a class="text-link" href="/web/materials/'
                + selected["material_id"]
                + "?part="
                + str(part["chunk_index"])
                + '">回到原文并换段 →</a></div>'
            )
            study_button = (
                '<input type="hidden" name="message" value=""><button class="button button-primary button-full" type="submit"'
                + (" disabled" if pending else "")
                + ">讲解并提炼这段</button>"
            )
            study_action = (
                dialogue_form(token, "study", study_button, study_id, form_part)
                if enabled
                else '<button class="button button-primary button-full" type="button" disabled>讲解并提炼这段</button>'
            )
            directory = study_directory(
                selected,
                materials_repository.chunks(user_id, selected["material_id"]),
                dialogue_repository.book_units(user_id, selected["material_id"]),
                dialogue_repository.book_coverage(user_id, selected["material_id"]),
                part["chunk_id"],
            )
            unit = directory["unit"]
            book_url = "/web/materials/" + selected["material_id"] + "/plan"
            summary += (
                '<div class="book-study-summary"><p>学习单元 · '
                + escape(unit["title"] if unit else "按原文顺序学习")
                + "</p><p>已讲解 "
                + str(unit["explained"] if unit else directory["explained"])
                + " / "
                + str(unit["total"] if unit else directory["total"])
                + ' 段</p><p class="learning-record-note">带原文引用的选段回复记录，不代表已经掌握。</p><a class="text-link" href="'
                + book_url
                + '">书籍学习目录与进度 →</a></div>'
            )
            following = directory["next"]
            if following:
                next_button = (
                    '<input type="hidden" name="message" value=""><button class="button button-outline button-full" type="submit"'
                    + (" disabled" if pending else "")
                    + ">讲解下一段 · "
                    + escape(following["locator"])
                    + "</button>"
                )
                if enabled:
                    study_action += dialogue_form(
                        token, "study", next_button, study_id, following["chunk_id"]
                    )
            else:
                study_action += (
                    '<p class="learning-record-note">已到'
                    + ("本单元" if unit else "可读原文")
                    + "末段；可重温当前段落，或到学习目录选择其他范围。</p>"
                )
            details = details.replace("</h3>", "</h3>" + summary + study_action, 1)
        elif stored_part:
            source_content += '<p class="form-error-summary">原选段暂不可用，请重新选择可读片段；系统不会改用其他段落。</p>'
        source_turns = (
            dialogue_repository.topic_turns(user_id, active_topic["topic_id"])
            if active_topic
            else view["turns"]
        )
        latest_sources = next(
            (
                turn.get("citations", [])
                for turn in reversed(source_turns)
                if turn["status"] == "complete"
            ),
            [],
        )
        source_content += "".join(
            '<details class="citation"><summary>最近回复引用：'
            + escape(source["title"] + " · " + source["locator"])
            + "</summary><p>"
            + escape(source["excerpt"])
            + "</p></details>"
            for source in latest_sources
        )
        assets_panel = (
            '<section class="workspace-assets" aria-label="知识资产沉淀"><h2><a href="/web/knowledge">知识资产沉淀</a></h2>'
            '<nav class="asset-nav" aria-label="教案收集与保存"><a href="/web/knowledge?status=pending">教案草稿 · 预览与保存'
            + ('<span class="asset-pending">待你确认</span>' if draft_items else "")
            + '</a><a href="/web/knowledge">已保存的教案目录</a><a href="/web/knowledge-favorites">常用教案 · 我的收藏</a><a href="/web/knowledge-removed">已移出草稿 · 找回</a><a href="/web/booklets">我的学习手册</a><a href="/web/export">导出我的学习资料</a></nav>'
            + lesson_button
            + "</section>"
        )
        review_content = (
            '<div class="review-note"><p>正在重温教案</p><a class="text-link" href="/web/knowledge/'
            + review["knowledge_id"]
            + '">'
            + escape(review["title"])
            + "</a></div>"
            if review
            else ""
        )
        panel = (
            '<section class="learning-status" aria-labelledby="learning-title"><p class="eyebrow">LEARNING COMPANION</p><h2 id="learning-title">当前学习主题</h2>'
            + details
            + button
            + '<a class="text-link study-directory-link" href="/web/studies">查看全部学习主题 →</a>'
            + '<p class="learning-return-note">临时聊别的，也会保留这里的学习位置。</p>'
            + '<div class="learning-sources"><h3>正在引用的书籍资料</h3>'
            + source_content
            + "</div>"
            + '<details class="workspace-help"><summary>对话记录与使用说明</summary><p>每批加载 40 轮（一问一答为一轮），上滑可继续加载更早记录。记录按账户保存在本机，不因超过 40 轮自动删除；实际容量取决于磁盘空间。每次可输入 2000 字。</p><p>学习进度由教练整理供你核对。教案先形成草稿，经你确认后保存到知识库。</p><p id="conversation-availability">'
            + escape(
                dialogue_label
                or ("对话已启用。" if enabled else "对话准备中，当前暂不能发送消息。")
            )
            + "</p></details></section>"
        )
        assets_panel += review_content
        return body, panel, assets_panel

    def dialogue_problem(message, code):
        body = f'<main id="main-content" class="verification-layout"><section class="verification-card"><h1>对话暂未完成</h1><p role="alert">{escape(message)}</p><a class="button button-primary" href="/web/welcome#conversation-input">返回对话</a></section></main>'
        return HTMLResponse(
            _render_layout("对话提示 · 知行", body, signed_in=True),
            status_code=code,
            headers=_HEADERS,
        )

    def perform_dialogue(
        user_id, message, nonce, action, *, study_id=None, part_id=None
    ):
        if not dialogue_slots.acquire(blocking=False):
            return "busy"
        try:
            return send_dialogue(
                dialogue_repository,
                user_id,
                message,
                nonce,
                responder=dialogue_responder,
                action=action,
                materials=materials_repository,
                study_id=study_id,
                part_id=part_id,
            )
        finally:
            dialogue_slots.release()

    @app.post(
        "/web/coach/message", response_class=HTMLResponse, include_in_schema=False
    )
    async def message(request: Request):
        try:
            account = await run_in_threadpool(
                signed_in_account, repository, request.cookies.get(SESSION_COOKIE)
            )
        except sqlite3.Error:
            return dialogue_problem("暂时无法核对账户，请稍后再试。", 503)
        if account is None:
            return redirect("/web/login")
        if not same_origin(request):
            return dialogue_problem("页面无法核对，请返回对话后重新发送。", 403)
        values = await fields(
            request,
            {"csrf", "nonce", "action", "message"},
            max_bytes=24576,
            optional={"study_id", "part_id"},
        )
        if values is None:
            return dialogue_problem("消息格式无法读取，请返回对话重新填写。", 400)
        if (
            re.fullmatch(r"[A-Za-z0-9_-]{43}", values["nonce"]) is None
            or values["action"] not in {"message", "continue", "lesson", "study"}
            or re.fullmatch(r"[0-9a-f]{64}", values["csrf"]) is None
            or (
                "study_id" in values
                and re.fullmatch(r"[0-9a-f]{32}", values["study_id"]) is None
            )
            or (
                "part_id" in values
                and (
                    "study_id" not in values
                    or re.fullmatch(r"(?:[0-9a-f]{32})?", values["part_id"]) is None
                )
            )
        ):
            return dialogue_problem("页面无法核对，请返回对话后重新发送。", 403)
        token = request.cookies.get(SESSION_COOKIE)
        expected = signature(
            "dialogue",
            f"{token}.{values['nonce']}.{values['action']}"
            + ("." + values["study_id"] if values.get("study_id") else "")
            + (".part:" + values["part_id"] if "part_id" in values else ""),
        )
        if not hmac.compare_digest(expected, values["csrf"]):
            return dialogue_problem("页面无法核对，请返回对话后重新发送。", 403)
        if dialogue_responder is None:
            return dialogue_problem("对话服务尚未启用。", 503)
        wait = dialogue_limit.admit(
            request.client.host if request.client else "unknown"
        )
        if wait:
            page = dialogue_problem(f"消息发送较频繁，请 {wait} 秒后再试。", 429)
            page.headers["Retry-After"] = str(wait)
            return page
        try:
            outcome = await run_in_threadpool(
                perform_dialogue,
                account.user_id,
                values["message"],
                values["nonce"],
                values["action"],
                study_id=values.get("study_id") or None,
                part_id=values.get("part_id"),
            )
        except ValueError:
            return dialogue_problem(
                "请输入 1 到 2000 字的消息；续学需要已有主题。资料或选段若已变化，请重新打开页面核对。",
                400,
            )
        except sqlite3.Error:
            return dialogue_problem(
                "对话记录暂时无法保存，请先返回查看，避免重复发送。", 503
            )
        if outcome == "busy":
            return dialogue_problem("还有回复正在处理中，请稍后返回查看。", 409)
        if outcome == "daily_limit":
            try:
                snapshot = dialogue_repository.ai_usage(account.user_id)
            except sqlite3.Error:
                return dialogue_problem(
                    "本次尚未受理，暂时无法核对每日用量，请稍后查看。", 503
                )
            text = usage_message(snapshot)
            if request.headers.get("accept") == "application/json":
                return JSONResponse(
                    {"code": "daily_ai_limit", "sent": False, "error": text},
                    status_code=429,
                    headers=_HEADERS,
                )
            return dialogue_problem(text, 429)
        if request.headers.get("accept") == "application/json":
            return JSONResponse(
                {"redirect": "/web/welcome#coach-dialog"}, headers=_HEADERS
            )
        return redirect("/web/welcome#coach-dialog")

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
