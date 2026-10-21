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
from coach.learning_topics import (
    TopicBusy,
    topic_key,
    validate_topic_title,
    discussion_part,
    topic_edit_version,
)
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

    async def fields(request, expected, *, limit=4096):
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            return None
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > limit:
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
        if (
            len(query) > 120
            or re.fullmatch(r"[1-9][0-9]{0,4}", number) is None
            or any(len(request.query_params.getlist(key)) > 1 for key in ("q", "page"))
        ):
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
        needle = topic_key(query)
        body = '<p class="study-intro">每个学习主题分别保留已讨论内容、下一步和关联资料。选择一个主题，就能回到自己的学习位置。</p>'
        body += (
            '<form class="study-search" method="get" action="/web/studies"><label for="study-query">查找学习主题</label><input id="study-query" type="search" name="q" maxlength="120" value="'
            + escape(query, quote=True)
            + '" placeholder="主题、已讨论内容或下一步" aria-describedby="study-search-help"><button class="button button-outline" type="submit">查找</button></form><p id="study-search-help" class="study-note">按当前保存的主题名称、已讨论内容和下一步查找。</p>'
        )
        if query:
            body += '<a class="text-link" href="/web/studies">查看全部主题 →</a>'
        if request.query_params.get("notice") == "existing":
            body += '<p class="study-notice" role="status">同名主题已经存在，已回到原来的位置，没有覆盖原进度或关联资料。</p>'
        if request.query_params.get("notice") == "edited":
            body += '<p class="study-notice" role="status">学习记录已保存。下次续学会参考当前记录，原书籍、选段和历史内容保留。</p>'
        if not records:
            body += (
                '<section class="library-card"><h2>'
                + ("没有找到匹配的学习记录" if query else "从一个想学的主题开始")
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
            matched = (
                '<p class="study-note">匹配位置：'
                + "、".join(
                    label
                    for field, label in (
                        ("title", "主题名称"),
                        ("progress", "已讨论"),
                        ("next_step", "下一步"),
                    )
                    if needle in topic_key(item[field])
                )
                + "</p>"
                if query
                else ""
            )
            body += (
                '<article class="library-card study-card"><div class="study-card-title"><h2>'
                + escape(item["title"])
                + "</h2>"
                + ('<span class="study-current">当前主题</span>' if active else "")
                + "</div>"
                + matched
                + "<dl><dt>已讨论</dt><dd>"
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
                + '">回看主题对话</a><a class="text-link" href="/web/studies/'
                + identity
                + '/edit">修改学习记录</a></div></article>'
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
        body += (
            '<section id="book-reading" class="library-card book-start"><h2>按书名开始导读</h2><p>不必先上传电子书。先了解主要观点，再结合你的生活、工作或学习讨论应用。</p><form method="post" action="/web/studies/book">'
            + hidden(request, "book")
            + '<label for="book-title">书名</label><input id="book-title" name="title" maxlength="80" placeholder="例如：影响力" required><label for="book-author">作者或版本（可选）</label><input id="book-author" name="author" maxlength="24" placeholder="帮助区分同名书和不同版本"><p class="study-note">此方式依据 AI 通用知识，尚未核对原书，不提供虚构页码。创建后回到同一个聊天框，确认发送才调用 AI；以后也可以关联上传的原书。</p><button class="button button-primary" type="submit">建立阅读主题，回到对话</button></form></section>'
        )
        return page("我的学习", body)

    @app.post("/web/studies/book", include_in_schema=False)
    async def create_book(request: Request):
        account, denied = auth(request, True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf", "title", "author"})
        if not valid(request, values, "book"):
            return problem("页面无法核对，请返回书名导读重新填写。", 403)
        try:
            book = validate_topic_title(values["title"])
            author = values["author"].strip()
            if len(book) > 80 or len(author) > 24:
                raise ValueError("书名最多 80 字，作者或版本最多 24 字。")
            if author:
                validate_topic_title(author)
            title = validate_topic_title(
                "阅读《" + book + "》" + (" · " + author if author else "")
            )
            result = await run_in_threadpool(
                dialogue.create_topic, account.user_id, title, ""
            )
        except TopicBusy as error:
            return problem(str(error), 409)
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("暂时无法建立阅读主题，请稍后再试。", 503)
        # Existing topics keep any original book binding and selected passage.
        return redirect(
            "/web/studies?notice=existing"
            if result == "existing"
            else "/web/welcome?book_intro=1#coach-dialog"
        )

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

    def editor(request, item, *, values=None, message="", code=200):
        version = topic_edit_version(item)
        values = values if values is not None else item
        body = '<p class="study-intro">需要时修正学习记录，按自己的节奏继续。修改不会发送给 AI，也不要求完成练习或提交评分；后续实际讨论仍会更新记录。</p>'
        if message:
            body += (
                '<p class="form-error-summary" role="alert">' + escape(message) + "</p>"
            )
        if code == 409:
            body += '<details class="library-card study-edit-current" open><summary>核对当前保存的记录</summary><dl>'
            for key, label in (
                ("title", "主题"),
                ("progress", "已讨论"),
                ("next_step", "下一步"),
            ):
                body += "<dt>" + label + "</dt><dd>" + escape(item[key]) + "</dd>"
            body += "</dl></details>"
        body += (
            '<section class="library-card study-edit"><h2>本次修改</h2><form method="post" action="/web/studies/'
            + item["topic_id"]
            + '/edit">'
            + hidden(request, "edit", item["topic_id"] + "." + version)
            + '<input type="hidden" name="version" value="'
            + version
            + '">'
            + '<label for="edit-topic-title">学习主题</label><input id="edit-topic-title" name="title" maxlength="120" required value="'
            + escape(values["title"], quote=True)
            + '">'
            + '<label for="edit-topic-progress">已讨论的内容</label><textarea id="edit-topic-progress" name="progress" rows="5" maxlength="800" required>'
            + escape(values["progress"])
            + "</textarea>"
            + '<label for="edit-topic-next">下一步</label><textarea id="edit-topic-next" name="next_step" rows="4" maxlength="800" required>'
            + escape(values["next_step"])
            + "</textarea>"
            + '<p class="study-note">只修改需要调整的内容。关联书籍和选段保留；这不是掌握程度评价。保存其他主题的记录不会切换当前对话。</p>'
            + '<div class="study-actions"><button class="button button-primary" type="submit">保存学习记录</button>'
            + '<a class="button button-outline" href="/web/studies">取消并返回我的学习</a></div></form></section>'
        )
        return page("修改学习记录", body, code)

    @app.get("/web/studies/{identity}/edit", include_in_schema=False)
    def edit_record(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            item = dialogue.topic(account.user_id, identity)
            if item is None:
                return problem("找不到这个学习主题。", 404)
            return editor(request, item)
        except sqlite3.Error:
            return problem("暂时无法读取学习记录，请稍后再试。", 503)

    @app.post("/web/studies/{identity}/edit", include_in_schema=False)
    async def save_record(request: Request, identity: str):
        account, denied = auth(request, True)
        if denied is not None:
            return denied
        values = await fields(
            request, {"csrf", "version", "title", "progress", "next_step"}, limit=24576
        )
        version = values["version"] if values else ""
        if not re.fullmatch(r"[a-f0-9]{64}", version) or not valid(
            request, values, "edit", identity + "." + version
        ):
            return problem("页面无法核对，请重新打开学习记录。", 403)
        try:
            item = await run_in_threadpool(dialogue.topic, account.user_id, identity)
            if item is None:
                return problem("找不到这个学习主题。", 404)
            try:
                outcome = await run_in_threadpool(
                    dialogue.edit_topic,
                    account.user_id,
                    identity,
                    values["title"],
                    values["progress"],
                    values["next_step"],
                    expected_version=version,
                )
            except TopicBusy:
                return editor(
                    request,
                    item,
                    values=values,
                    message="教练还在回复，请等本轮结束后再保存。你的填写保留在下面。",
                    code=409,
                )
            except ValueError as error:
                return editor(
                    request, item, values=values, message=str(error), code=400
                )
            if outcome == "missing":
                return problem("找不到这个学习主题。", 404)
            if outcome in {"conflict", "duplicate"}:
                item = await run_in_threadpool(
                    dialogue.topic, account.user_id, identity
                )
                if item is None:
                    return problem("找不到这个学习主题。", 404)
                return editor(
                    request,
                    item,
                    values=values,
                    message=(
                        "学习记录已在其他页面或新一轮对话中更新。请核对当前记录和本次填写，再决定是否保存。"
                        if outcome == "conflict"
                        else "已有同名学习主题，请更换名称；不会合并主题或覆盖另一份进度。"
                    ),
                    code=409,
                )
            return redirect("/web/studies?notice=edited")
        except sqlite3.Error:
            return problem("暂时无法保存学习记录，请稍后再试。", 503)

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
