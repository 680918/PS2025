"""Owned multi-topic directory, explicit activation and user-triggered continuation."""

import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import parse_qs, quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from api.library_pages import HEADERS, library_csrf
from api.public_pages import _render_layout
from coach.learning_topics import TopicBusy, validate_topic_title, discussion_part
from coach.ai_usage import usage_message
from security.login_sessions import signed_in_account
from security.registration_rate_limit import RegistrationRateLimiter


def register_study_pages(
    app, accounts, dialogue, materials, *, csrf_key, enabled, resume
):
    views = RegistrationRateLimiter(per_client_limit=60, total_limit=600)
    writes = RegistrationRateLimiter(per_client_limit=8, total_limit=80)

    def page(title, body, code=200):
        content = '<main id="main-content" class="library-space study-space"><nav class="library-tabs" aria-label="工作区入口"><a href="/web/welcome">← 回到对话</a><a href="/web/studies" aria-current="page">我的学习</a><a href="/web/materials">资料与书籍</a><a href="/web/knowledge">知识资产沉淀</a><a href="/web/memories">我的学习记忆</a><a href="/web/export">导出学习资料</a></nav>'
        content += (
            "<h1>"
            + escape(title)
            + "</h1>"
            + body
            + '</main><script src="/static/study-navigation.js" defer></script>'
        )
        return HTMLResponse(
            _render_layout(title + " · 知行", content, signed_in=True),
            status_code=code,
            headers={
                **HEADERS,
                "Content-Security-Policy": "default-src 'none'; style-src 'self'; script-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            },
        )

    def problem(text, code=400):
        return page(
            "学习操作暂未完成",
            '<p class="form-error-summary" role="alert">'
            + escape(text)
            + '</p><a class="button button-outline" href="/web/studies">回到我的学习</a><a class="text-link" href="/web/welcome">查看当前对话 →</a>',
            code,
        )

    def redirect(path):
        return RedirectResponse(path, status_code=303, headers=HEADERS)

    def auth(request, write=False):
        wait = (writes if write else views).admit(
            request.client.host if request.client else "unknown"
        )
        if wait:
            result = problem("操作较频繁，请稍后再试。", 429)
            result.headers["Retry-After"] = str(wait)
            return None, result
        try:
            account = signed_in_account(
                accounts, request.cookies.get("coach_login_session")
            )
        except sqlite3.Error:
            return None, problem("暂时无法核对登录状态。", 503)
        return (account, None) if account else (None, redirect("/web/login"))

    def csrf(request, purpose, identity=""):
        return library_csrf(
            csrf_key,
            request.cookies.get("coach_login_session", ""),
            "study-" + purpose,
            identity,
        )

    def hidden(request, purpose, identity=""):
        return (
            '<input type="hidden" name="csrf" value="'
            + csrf(request, purpose, identity)
            + '">'
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
            result = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                encoding="utf-8",
                errors="strict",
                max_num_fields=len(expected),
            )
        except (ValueError, UnicodeError):
            return None
        return (
            {key: value[0] for key, value in result.items()}
            if set(result) == expected
            and all(len(value) == 1 for value in result.values())
            else None
        )

    def valid(request, values, purpose, identity=""):
        origin, site = (
            request.headers.get("origin"),
            request.headers.get("sec-fetch-site"),
        )
        same = origin in {None, f"{request.url.scheme}://{request.url.netloc}"} or (
            origin == "null" and site == "same-origin"
        )
        return (
            values is not None
            and site != "cross-site"
            and same
            and re.fullmatch(r"[a-f0-9]{64}", values["csrf"]) is not None
            and secrets.compare_digest(values["csrf"], csrf(request, purpose, identity))
        )

    @app.get("/web/studies", include_in_schema=False)
    def index(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        query = request.query_params.get("q", "").strip()
        number = request.query_params.get("page", "1")
        if len(query) > 120 or re.fullmatch(r"[1-9][0-9]{0,4}", number) is None:
            return problem("请检查主题搜索文字和目录页码。")
        try:
            records = dialogue.list_topics(
                account.user_id, query=query, offset=(int(number) - 1) * 10, limit=11
            )
            current = dialogue.active_topic(account.user_id)
            books = materials.list(account.user_id) if materials else []
        except sqlite3.Error:
            return problem("暂时无法读取学习主题。", 503)
        by_id = {item["material_id"]: item for item in books}
        body = '<p class="study-intro">每个学习主题分别保留已讨论内容、下一步和关联资料。选择一个主题，就能回到自己的学习位置。</p>'
        body += (
            '<form class="study-search" method="get" action="/web/studies"><label for="study-query">查找学习主题</label><input id="study-query" type="search" name="q" maxlength="120" value="'
            + escape(query, quote=True)
            + '"><button class="button button-outline" type="submit">查找</button></form>'
        )
        if request.query_params.get("notice") == "existing":
            body += '<p class="study-notice" role="status">同名主题已经存在，已回到原来的位置，没有覆盖原进度或关联资料。</p>'
        if not records:
            body += (
                '<section class="library-card"><h2>'
                + ("没有找到这个主题" if query else "从一个想学的主题开始")
                + "</h2><p>可以在下方新建，也可以回到对话说“我想学习……”；教练明确记录新的学习主题后，会出现在这里。</p></section>"
            )
        body += '<div class="study-list">'
        for item in records[:10]:
            identity = item["topic_id"]
            active = current is not None and current["topic_id"] == identity
            material = by_id.get(item["material_id"])
            material_title = (
                material["title"]
                if material
                else "资料已不可用，请重新选择"
                if item["material_id"]
                else "未关联资料"
            )
            selected_part = discussion_part(
                dialogue, materials, account.user_id, topic_id=identity
            )
            if selected_part:
                material_title += " · " + selected_part["locator"]
            stamp = datetime.fromtimestamp(
                item["updated_at"], timezone(timedelta(hours=8))
            ).strftime("%Y-%m-%d %H:%M")
            body += (
                '<article class="library-card study-card"><div class="study-card-title"><h2>'
                + escape(item["title"])
                + "</h2>"
                + ('<span class="study-current">当前主题</span>' if active else "")
                + "</div><dl><dt>已讨论</dt><dd>"
                + escape(item["progress"])
                + "</dd><dt>下一步</dt><dd>"
                + escape(item["next_step"])
                + "</dd><dt>关联资料</dt><dd>"
                + escape(material_title)
                + '</dd></dl><p class="study-meta">更新于 '
                + stamp
                + ' · 北京时间</p><div class="study-actions">'
            )
            nonce = secrets.token_urlsafe(32)
            body += (
                '<form data-study-resume method="post" action="/web/studies/'
                + identity
                + '/continue">'
                + hidden(request, "continue", identity + "." + nonce)
                + '<input type="hidden" name="nonce" value="'
                + nonce
                + '"><button class="button button-primary" type="submit"'
                + ("" if enabled else " disabled")
                + '>继续学习</button><p class="study-wait" role="status" hidden></p></form>'
            )
            body += (
                '<form method="post" action="/web/studies/'
                + identity
                + '/open">'
                + hidden(request, "open", identity)
                + '<button class="button button-outline" type="submit">只切换主题</button></form><a class="text-link" href="/web/conversations?topic='
                + identity
                + '">回看主题对话</a></div></article>'
            )
        body += '</div><nav class="library-paging" aria-label="主题目录分页">'
        base = "/web/studies?q=" + quote(query, safe="") + "&amp;page="
        if int(number) > 1:
            body += (
                '<a class="text-link" href="'
                + base
                + str(int(number) - 1)
                + '">← 上一页</a>'
            )
        if len(records) > 10:
            body += (
                '<a class="text-link" href="'
                + base
                + str(int(number) + 1)
                + '">下一页 →</a>'
            )
        body += '</nav><p class="study-note">查看目录和只切换主题不调用 AI；点击“继续学习”会让教练接着回复，使用当前配置的 AI 服务。正在回复时，请等本轮结束再切换。</p>'
        options = '<option value="">暂不关联资料</option>' + "".join(
            '<option value="'
            + item["material_id"]
            + '">'
            + escape(item["title"])
            + "</option>"
            for item in books
        )
        body += (
            '<section class="library-card study-add"><h2>新建学习主题</h2><form method="post" action="/web/studies/new">'
            + hidden(request, "new")
            + '<label for="study-title">你想学习什么？</label><input id="study-title" name="title" maxlength="120" placeholder="例如：Python 入门、阅读《学习之道》" required><label for="study-material">关联资料（可选）</label><select id="study-material" name="material_id">'
            + options
            + '</select><p class="study-note">新建后回到统一对话，由你决定何时开始提问。也可到“资料与书籍”为当前主题选择或取消资料。</p><button class="button button-primary" type="submit">创建并回到对话</button></form></section>'
        )
        return page("我的学习", body)

    @app.post("/web/studies/new", include_in_schema=False)
    async def create(request: Request):
        account, denied = auth(request, True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf", "title", "material_id"})
        if not valid(request, values, "new"):
            return problem("页面无法核对，请返回目录重新填写。", 403)
        try:
            title = validate_topic_title(values["title"])
            identity = values["material_id"]
            if identity and (
                materials is None or materials.get(account.user_id, identity) is None
            ):
                return problem("找不到这份本人资料，请重新选择。", 404)
            result = await run_in_threadpool(
                dialogue.create_topic, account.user_id, title, identity
            )
        except TopicBusy as error:
            return problem(str(error), 409)
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("暂时无法保存学习主题，请稍后再试。", 503)
        return redirect(
            "/web/studies?notice=existing"
            if result == "existing"
            else "/web/welcome#coach-dialog"
        )

    @app.post("/web/studies/{identity}/{operation}", include_in_schema=False)
    async def choose(request: Request, identity: str, operation: str):
        account, denied = auth(request, True)
        if denied is not None:
            return denied
        if (
            operation not in {"open", "continue"}
            or re.fullmatch(r"[a-f0-9]{32}", identity) is None
        ):
            return problem("找不到这个学习操作。", 404)
        values = await fields(
            request, {"csrf", "nonce"} if operation == "continue" else {"csrf"}
        )
        nonce = values.get("nonce", "") if values else ""
        if (
            operation == "continue"
            and re.fullmatch(r"[A-Za-z0-9_-]{43}", nonce) is None
        ):
            return problem("续学页面无法核对，请返回目录。", 403)
        if not valid(
            request,
            values,
            operation,
            identity + ("." + nonce if operation == "continue" else ""),
        ):
            return problem("页面无法核对，请返回目录重新打开。", 403)
        try:
            if dialogue.topic(account.user_id, identity) is None:
                return problem("找不到这个学习主题。", 404)
            if operation == "open":
                await run_in_threadpool(
                    dialogue.activate_topic, account.user_id, identity
                )
            else:
                if not enabled:
                    return problem(
                        "AI 对话尚未启用，可以先使用‘只切换主题’查看学习位置。", 503
                    )
                outcome = await run_in_threadpool(
                    resume, account.user_id, identity, nonce
                )
                if outcome == "busy":
                    return problem("教练还在回复，请稍后再继续。", 409)
                if outcome == "daily_limit":
                    return problem(
                        usage_message(dialogue.ai_usage(account.user_id)), 429
                    )
        except TopicBusy as error:
            return problem(str(error), 409)
        except ValueError:
            return problem("无法恢复这个学习主题，请返回目录重试。", 404)
        except sqlite3.Error:
            return problem("暂时无法读取学习位置，请先查看当前对话。", 503)
        return redirect("/web/welcome#coach-dialog")
