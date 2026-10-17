"""Private learning-note management; all mutations are explicit, no AI calls."""

import re
import secrets
import sqlite3
from html import escape
from urllib.parse import parse_qs

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from api.library_pages import HEADERS, library_csrf
from api.public_pages import _render_layout
from coach.learning_memory import MAX_MEMORIES, MemoryInputError, validate_memory
from security.login_sessions import signed_in_account
from security.registration_rate_limit import RegistrationRateLimiter


def register_memory_pages(app, accounts, dialogue, *, csrf_key):
    views = RegistrationRateLimiter(per_client_limit=60, total_limit=600)
    writes = RegistrationRateLimiter(per_client_limit=12, total_limit=60)

    def page(title, body, *, code=200):
        content = (
            '<main id="main-content" class="library-space memory-space"><nav class="library-tabs" aria-label="工作区入口">'
            '<a href="/web/welcome">← 回到对话</a><a href="/web/studies">我的学习</a><a href="/web/materials">资料与书籍</a>'
            '<a href="/web/knowledge">知识资产沉淀</a><a href="/web/memories" aria-current="page">我的学习记忆</a><a href="/web/export">导出学习资料</a></nav>'
            f"<h1>{escape(title)}</h1>{body}</main>"
        )
        return HTMLResponse(
            _render_layout(title + " · 知行", content, signed_in=True),
            status_code=code,
            headers=HEADERS,
        )

    def redirect(path):
        return RedirectResponse(path, status_code=303, headers=HEADERS)

    def problem(text, code=400):
        return page(
            "操作暂未完成",
            f'<p class="form-error-summary" role="alert">{escape(text)}</p><a class="button button-outline" href="/web/memories">返回我的学习记忆</a>',
            code=code,
        )

    def auth(request, *, write=False):
        wait = (writes if write else views).admit(
            request.client.host if request.client else "unknown"
        )
        if wait:
            result = problem("操作较频繁，请稍后重试。", 429)
            result.headers["Retry-After"] = str(wait)
            return None, result
        try:
            account = signed_in_account(
                accounts, request.cookies.get("coach_login_session")
            )
        except sqlite3.Error:
            return None, problem("暂时无法读取登录状态，请稍后重试。", 503)
        return (account, None) if account else (None, redirect("/web/login"))

    def signature(request, purpose, identity=""):
        return library_csrf(
            csrf_key,
            request.cookies.get("coach_login_session", ""),
            "memory-" + purpose,
            identity,
        )

    def hidden(request, purpose, identity=""):
        return (
            '<input type="hidden" name="csrf" value="'
            + signature(request, purpose, identity)
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
                max_num_fields=len(expected),
                encoding="utf-8",
                errors="strict",
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
        origin = request.headers.get("origin")
        fetch_site = request.headers.get("sec-fetch-site")
        # Embedded browser form submissions may have an opaque Origin. Accept
        # that case only with same-origin browser metadata AND the bound CSRF.
        origin_matches = origin in {
            None,
            f"{request.url.scheme}://{request.url.netloc}",
        } or (origin == "null" and fetch_site == "same-origin")
        return (
            values is not None
            and fetch_site != "cross-site"
            and origin_matches
            and re.fullmatch(r"[a-f0-9]{64}", values["csrf"]) is not None
            and secrets.compare_digest(
                values["csrf"], signature(request, purpose, identity)
            )
        )

    def entry(user_id, memory_id):
        if re.fullmatch(r"[a-f0-9]{32}", memory_id) is None:
            return None
        return dialogue.memory(user_id, memory_id)

    def editor(request, note, *, content=None, message="", code=200):
        identity = note["memory_id"]
        version = str(note["revision"])
        error = (
            '<p class="form-error-summary" role="alert">' + escape(message) + "</p>"
            if message
            else ""
        )
        current = (
            '<p class="memory-caption">当前保存的内容：</p><p class="memory-content">'
            + escape(note["content"])
            + "</p>"
            if code == 409
            else ""
        )
        body = (
            error
            + current
            + '<section class="library-card"><form method="post" action="/web/memories/'
            + identity
            + '">'
        )
        body += (
            hidden(request, "edit", identity + "." + version)
            + '<input type="hidden" name="revision" value="'
            + version
            + '">'
        )
        body += (
            '<label for="memory-content">这条学习记忆</label><textarea id="memory-content" name="content" rows="5" maxlength="300" required>'
            + escape(note["content"] if content is None else content)
            + "</textarea>"
        )
        body += '<p class="memory-caption">修改会用于之后新发起的交流，不会改写聊天记录或已经发送给 AI 的内容。</p><div class="memory-actions"><button class="button button-primary" type="submit">保存修改</button><a class="button button-outline" href="/web/memories">取消</a></div></form></section>'
        return page("修改学习记忆", body, code=code)

    @app.get("/web/memories", include_in_schema=False)
    def index(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            notes = dialogue.list_memories(account.user_id)
        except sqlite3.Error:
            return problem("暂时无法读取学习记忆，请稍后重试。", 503)
        messages = {
            "added": "学习记忆已保存。",
            "existing": "这条内容已经保存，无需重复添加。",
            "updated": "学习记忆已修改，之后的交流会参考新内容。",
            "deleted": "这条长期记忆已删除，后续不会再作为长期记忆提供。",
        }
        notice = messages.get(request.query_params.get("done"), "")
        body = '<p class="memory-lead">留下你希望 Coach 长期参考的学习目标、基础和讲解偏好。这里只保存你明确要求记住或主动填写的内容。</p>'
        body += '<p class="memory-caption">这些记忆会随之后的问题提供给当前 AI 服务。普通聊天、上传资料和 Coach 的推测不会自动保存到这里。</p>'
        body += f'<p class="memory-count">已保存 {len(notes)} / {MAX_MEMORIES} 条 · 每条最多 300 字</p>'
        if notice:
            body += '<p class="memory-notice" role="status">' + notice + "</p>"
        body += '<div class="memory-list">'
        for note in notes:
            body += (
                '<article class="library-card memory-card"><p class="memory-content">'
                + escape(note["content"])
                + '</p><div class="memory-actions"><a class="text-link" href="/web/memories/'
                + note["memory_id"]
                + '">修改</a><a class="text-link" href="/web/memories/'
                + note["memory_id"]
                + '/delete">删除</a></div></article>'
            )
        if not notes:
            body += '<section class="library-card memory-empty"><h2>从一条简单的偏好开始</h2><p>在对话中说：“请记住，我喜欢先看例子再看概念。”</p><p>以后继续交流时，Coach 就能参考这条信息；不需要每轮重复填写。</p></section>'
        body += (
            '</div><section class="library-card memory-add" id="add-memory"><h2>添加一条学习记忆</h2><form method="post" action="/web/memories/add">'
            + hidden(request, "add")
        )
        body += '<label for="new-memory">希望 Coach 记住什么？</label><textarea id="new-memory" name="content" rows="3" maxlength="300" placeholder="例如：我正在自学 Python，希望通过小项目练习。" required></textarea><p class="memory-caption">请只填写愿意用于个性化交流的学习信息，不要放入密码、验证码或密钥。这里的添加、修改和删除不调用 AI。</p><button class="button button-primary" type="submit">保存这条记忆</button></form></section>'
        body += '<p class="memory-caption">删除只移除这条长期记忆，不会删除聊天里你曾说过的话，也无法撤回已发送给 AI 的内容。需要留存时，可在“导出学习资料”中选择学习记忆。</p>'
        return page("我的学习记忆", body)

    @app.post("/web/memories/add", include_in_schema=False)
    async def add(request: Request):
        account, denied = auth(request, write=True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf", "content"})
        if not valid(request, values, "add"):
            return problem("页面无法核对或填写内容无法读取，请返回后重新填写。", 403)
        try:
            result = dialogue.add_memory(
                account.user_id, validate_memory(values["content"])
            )
        except MemoryInputError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("暂时无法保存学习记忆，请稍后重试。", 503)
        if result == "full":
            return problem("学习记忆已达到 20 条，请先修改或删除不再适用的内容。", 409)
        return redirect(
            "/web/memories?done=" + ("added" if result == "created" else "existing")
        )

    @app.get("/web/memories/{memory_id}", include_in_schema=False)
    def edit(request: Request, memory_id: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            note = entry(account.user_id, memory_id)
        except sqlite3.Error:
            return problem("暂时无法读取学习记忆。", 503)
        return (
            editor(request, note) if note else problem("这条记忆不存在或已删除。", 404)
        )

    @app.post("/web/memories/{memory_id}", include_in_schema=False)
    async def update(request: Request, memory_id: str):
        return await change(request, memory_id, deleting=False)

    @app.get("/web/memories/{memory_id}/delete", include_in_schema=False)
    def delete_confirmation(request: Request, memory_id: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            note = entry(account.user_id, memory_id)
        except sqlite3.Error:
            return problem("暂时无法读取学习记忆。", 503)
        if note is None:
            return problem("这条记忆不存在或已删除。", 404)
        version = str(note["revision"])
        body = (
            '<section class="library-card"><p>确定删除这条长期记忆吗？</p><p class="memory-content">'
            + escape(note["content"])
            + '</p><p class="memory-caption">删除后不会再作为长期记忆提供给之后的新请求。聊天中的原话、已有回复和已发给 AI 的内容不受影响。此操作无法在页面恢复。</p>'
        )
        body += (
            '<form method="post" action="/web/memories/'
            + memory_id
            + '/delete">'
            + hidden(request, "delete", memory_id + "." + version)
            + '<input type="hidden" name="revision" value="'
            + version
            + '"><div class="memory-actions"><button class="button button-outline" type="submit">确认删除这条记忆</button><a class="button button-primary" href="/web/memories">保留，返回</a></div></form></section>'
        )
        return page("删除学习记忆", body)

    @app.post("/web/memories/{memory_id}/delete", include_in_schema=False)
    async def remove(request: Request, memory_id: str):
        return await change(request, memory_id, deleting=True)

    async def change(request, memory_id, *, deleting):
        account, denied = auth(request, write=True)
        if denied is not None:
            return denied
        values = await fields(
            request,
            {"csrf", "revision"} if deleting else {"csrf", "revision", "content"},
        )
        if (
            values is None
            or re.fullmatch(r"[1-9][0-9]{0,17}", values.get("revision", "")) is None
        ):
            return problem("无法读取表单，请返回学习记忆后重试。")
        version = values["revision"]
        if not valid(
            request, values, "delete" if deleting else "edit", memory_id + "." + version
        ):
            return problem("页面无法核对，请返回学习记忆后重新打开。", 403)
        try:
            note = entry(account.user_id, memory_id)
            if note is None:
                return problem("这条记忆不存在或已删除。", 404)
            if deleting:
                result = dialogue.delete_memory(
                    account.user_id, memory_id, int(version)
                )
            else:
                content = validate_memory(values["content"])
                result = dialogue.update_memory(
                    account.user_id, memory_id, content, int(version)
                )
            if result == "missing":
                return problem("这条记忆不存在或已删除。", 404)
            if result == "conflict":
                if deleting:
                    return problem(
                        "这条记忆已被其他页面修改，请重新打开、核对后再决定是否删除。",
                        409,
                    )
                latest = entry(account.user_id, memory_id)
                if latest is None:
                    return problem("这条记忆已经删除，请返回目录。", 404)
                return editor(
                    request,
                    latest,
                    content=content,
                    message="这条记忆已在其他页面更新。请比较当前内容和下方未保存的填写内容，再决定是否覆盖。",
                    code=409,
                )
            if result == "existing":
                return editor(
                    request,
                    note,
                    content=content,
                    message="相同内容已经在另一条记忆中，请合并或保留不同内容。",
                    code=409,
                )
        except MemoryInputError as error:
            return editor(
                request, note, content=values["content"], message=str(error), code=400
            )
        except sqlite3.Error:
            return problem("暂时无法修改学习记忆，请返回核对后再试。", 503)
        return redirect("/web/memories?done=" + ("deleted" if deleting else "updated"))
