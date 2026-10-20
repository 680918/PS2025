"""Organize saved lessons into private reading booklets; no model calls."""

import re
import sqlite3
from html import escape
from urllib.parse import parse_qs, quote, urlencode
from uuid import uuid4

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from api.asset_export import booklet_document
from api.coach_markdown import coach_markdown
from api.library_pages import HEADERS, library_csrf, search_excerpt
from api.public_pages import _render_layout
from coach.booklets import booklet_markdown, booklet_position_text
from coach.unit_lessons import unit_scope_text
from coach.knowledge_search import search_query, lesson_match
from security.login_sessions import signed_in_account
from security.registration_rate_limit import RegistrationRateLimiter
import secrets


def register_booklet_pages(app, accounts, dialogue, *, csrf_key):
    view_limit = RegistrationRateLimiter(per_client_limit=80, total_limit=800)
    write_limit = RegistrationRateLimiter(per_client_limit=30, total_limit=200)

    def page(title, body, *, code=200):
        content = (
            '<main id="main-content" class="library-space"><nav class="library-tabs" aria-label="知识资产入口"><a href="/web/welcome">← 回到对话</a><a href="/web/knowledge">已保存教案</a><a href="/web/booklets">我的学习手册</a><a href="/web/materials">资料与书籍</a><a href="/web/export">导出学习资料</a></nav><h1>'
            + escape(title)
            + "</h1>"
            + body
            + "</main>"
        )
        return HTMLResponse(
            _render_layout(title + " · 知行", content, signed_in=True),
            status_code=code,
            headers=HEADERS,
        )

    def problem(message, code=400):
        return page(
            "操作暂未完成",
            '<p class="form-error-summary" role="alert">'
            + escape(message)
            + '</p><a class="button button-outline" href="/web/booklets">返回学习手册</a>',
            code=code,
        )

    def redirect(path):
        return RedirectResponse(path, status_code=303, headers=HEADERS)

    def auth(request, *, write=False):
        wait = (write_limit if write else view_limit).admit(
            request.client.host if request.client else "unknown"
        )
        if wait:
            response = problem("操作较频繁，请稍后再试。", 429)
            response.headers["Retry-After"] = str(wait)
            return None, response
        try:
            account = signed_in_account(
                accounts, request.cookies.get("coach_login_session")
            )
        except sqlite3.Error:
            return None, problem("暂时无法核对登录状态。", 503)
        return (account, None) if account else (None, redirect("/web/login"))

    def csrf(request, purpose, binding):
        return library_csrf(
            csrf_key,
            request.cookies.get("coach_login_session", ""),
            "booklet-" + purpose,
            binding,
        )

    def hidden(request, purpose, binding):
        return (
            '<input type="hidden" name="csrf" value="'
            + csrf(request, purpose, binding)
            + '">'
        )

    async def fields(request, expected):
        if (
            request.headers.get("content-type", "").split(";", 1)[0]
            != "application/x-www-form-urlencoded"
        ):
            return None
        body = bytearray()
        async for piece in request.stream():
            if len(body) + len(piece) > 8192:
                return None
            body.extend(piece)
        try:
            parsed = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=len(expected),
                errors="strict",
            )
        except (ValueError, UnicodeError):
            return None
        if set(parsed) != expected or any(len(value) != 1 for value in parsed.values()):
            return None
        return {key: value[0] for key, value in parsed.items()}

    def valid(request, values, purpose, binding):
        origin = request.headers.get("origin")
        return (
            values is not None
            and request.headers.get("sec-fetch-site") != "cross-site"
            and origin in {None, f"{request.url.scheme}://{request.url.netloc}", "null"}
            and (
                origin != "null"
                or request.headers.get("sec-fetch-site") == "same-origin"
            )
            and bool(re.fullmatch(r"[a-f0-9]{64}", values.get("csrf", "")))
            and secrets.compare_digest(values["csrf"], csrf(request, purpose, binding))
        )

    def query_values(query):
        q = search_query(query.get("q", ""))
        number = query.get("page", "1")
        if len(q) > 120 or not re.fullmatch(r"[1-9][0-9]{0,5}", number):
            raise ValueError("请检查查找内容或目录页码。")
        return q, int(number)

    def new_form(request, *, identity=None, title="", message="", code=200):
        identity = identity or uuid4().hex
        body = '<p class="library-intro">先为手册起个名字，再从已保存教案中收录章节。整理目录不调用 AI。</p>'
        if message:
            body += (
                '<p class="form-error-summary" role="alert">' + escape(message) + "</p>"
            )
        body += (
            '<section class="library-card"><form method="post" action="/web/booklets/new">'
            + hidden(request, "create", identity)
            + '<input type="hidden" name="identity" value="'
            + identity
            + '"><label for="booklet-title">学习手册名称</label><input id="booklet-title" name="title" maxlength="120" required value="'
            + escape(title, quote=True)
            + '"><div class="library-actions"><button class="button button-primary" type="submit">创建并收录教案</button><a class="button button-outline" href="/web/booklets">返回手册目录</a></div></form></section>'
        )
        return page("创建学习手册", body, code=code)

    @app.get("/web/booklets", include_in_schema=False)
    def directory(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            q, number = query_values(request.query_params)
            books = dialogue.list_booklets(
                account.user_id, query=q, offset=(number - 1) * 20
            )
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("暂时无法读取手册目录。", 503)
        body = (
            '<p class="library-intro">把已经保存的知识组织成一本本可以重温的学习手册。原教案继续保留，手册按你的顺序呈现。</p><div class="library-actions"><a class="button button-primary" href="/web/booklets/new">创建学习手册</a><a class="text-link" href="/web/knowledge">查看已保存教案 →</a></div><form class="library-search" method="get"><label class="visually-hidden" for="booklet-query">查找手册名称</label><input id="booklet-query" name="q" maxlength="120" placeholder="查找手册名称" value="'
            + escape(q, quote=True)
            + '"><button class="button button-outline">查找</button></form><div class="booklet-list">'
        )
        if not books:
            body += '<section class="library-card"><h2>从一份教案开始积累</h2><p>可以按学习主题、书籍或个人目标创建手册，再逐渐收录已经确认保存的教案。</p></section>'
        for book in books[:20]:
            url = "/web/booklets/" + book["booklet_id"]
            position = book["reading_position"]
            position_note = (
                "已记到第 " + str(position["number"]) + " 章，下次从这里继续。"
                if position["number"]
                else (
                    "之前记住的章节已移出或暂不可用，请重新选择。"
                    if position["knowledge_id"]
                    else "尚未记住续读位置，可在阅读时保存。"
                )
            )
            body += (
                '<article class="library-card"><span class="library-badge">学习手册 · '
                + str(book["chapter_count"])
                + ' 章</span><h2><a href="'
                + url
                + '">'
                + escape(book["title"])
                + "</a></h2><p>"
                + position_note
                + '</p><div class="library-actions"><a class="button button-primary" href="'
                + url
                + ("#booklet-reading" if position["number"] else "")
                + '">'
                + ("继续阅读" if position["number"] else "打开阅读")
                + '</a><a class="text-link" href="'
                + url
                + '/edit">收录教案与整理目录</a></div></article>'
            )
        body += '</div><nav class="library-paging" aria-label="手册目录分页">'
        if number > 1:
            body += (
                '<a href="?'
                + urlencode({"q": q, "page": number - 1})
                + '">← 上一页</a>'
            )
        if len(books) > 20:
            body += (
                '<a href="?'
                + urlencode({"q": q, "page": number + 1})
                + '">下一页 →</a>'
            )
        return page("我的学习手册", body + "</nav>")

    @app.get("/web/booklets/new", include_in_schema=False)
    def create_page(request: Request):
        _, denied = auth(request)
        return denied if denied is not None else new_form(request)

    @app.post("/web/booklets/new", include_in_schema=False)
    async def create(request: Request):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(request, {"identity", "title", "csrf"})
        identity = values.get("identity", "") if values else ""
        if not re.fullmatch(r"[a-f0-9]{32}", identity) or not valid(
            request, values, "create", identity
        ):
            return problem("页面无法核对，请重新打开创建手册。", 403)
        try:
            result = await run_in_threadpool(
                dialogue.create_booklet, account.user_id, identity, values["title"]
            )
            if result == "missing":
                return problem("手册编号无法核对，请重新创建。", 404)
        except ValueError as error:
            return new_form(
                request,
                identity=identity,
                title=values["title"],
                message=str(error),
                code=400,
            )
        except sqlite3.Error:
            return problem("手册暂时无法保存，请先查看目录，避免重复创建。", 503)
        return redirect("/web/booklets/" + identity + "/edit")

    def edit_page(request, account, book, *, title=None, message="", code=200):
        q, number = query_values(request.query_params)
        # POST rerenders carry the last search, without hiding unsaved title text.
        if hasattr(request.state, "booklet_search"):
            q, number = request.state.booklet_search
        candidates = dialogue.list_knowledge(
            account.user_id, query=q, offset=(number - 1) * 20
        )
        url = "/web/booklets/" + book["booklet_id"]
        revision = str(book["revision"])
        ids = {item["knowledge_id"] for item in book["chapters"]}

        def action(operation, identity, label, *, disabled=False):
            binding = book["booklet_id"] + "." + revision + "." + identity
            return (
                '<form method="post" action="'
                + url
                + "/"
                + operation
                + '">'
                + hidden(request, operation, binding)
                + '<input type="hidden" name="revision" value="'
                + revision
                + '"><input type="hidden" name="knowledge_id" value="'
                + identity
                + '"><input type="hidden" name="q" value="'
                + escape(q, quote=True)
                + '"><input type="hidden" name="page" value="'
                + str(number)
                + '"><button class="button button-outline" type="submit"'
                + (" disabled" if disabled else "")
                + ">"
                + escape(label)
                + "</button></form>"
            )

        body = (
            '<p class="library-intro">收录、排序和移出只改变这本手册的目录，原教案仍保留。一本手册最多 100 章，当前 '
            + str(len(book["chapters"]))
            + ' 章。</p><div class="library-actions"><a class="button button-primary" href="'
            + url
            + '">打开手册阅读</a><a class="text-link" href="#booklet-add">查找并收录教案 ↓</a></div>'
        )
        if message:
            body += (
                '<p class="form-error-summary" role="alert">' + escape(message) + "</p>"
            )
        body += (
            '<section class="library-card"><form method="post" action="'
            + url
            + '/title">'
            + hidden(request, "title", book["booklet_id"] + "." + revision)
            + '<input type="hidden" name="revision" value="'
            + revision
            + '"><input type="hidden" name="q" value="'
            + escape(q, quote=True)
            + '"><input type="hidden" name="page" value="'
            + str(number)
            + '"><label for="booklet-title">手册名称</label><input id="booklet-title" name="title" maxlength="120" required value="'
            + escape(book["title"] if title is None else title, quote=True)
            + '"><button class="button button-outline" type="submit">保存名称</button></form></section><h2>手册目录</h2><ol class="booklet-chapters">'
        )
        if not book["chapters"]:
            body += '<li class="library-card">目录还是空的。到下方查找并收录一份已保存教案。</li>'
        for item in book["chapters"]:
            body += (
                '<li class="library-card"><h3>第 '
                + str(item["number"])
                + " 章 · "
                + escape(item["title"])
                + '</h3><div class="booklet-moves">'
                + action(
                    "up", item["knowledge_id"], "上移", disabled=item["number"] == 1
                )
                + action(
                    "down",
                    item["knowledge_id"],
                    "下移",
                    disabled=item["number"] == len(book["chapters"]),
                )
                + action("remove", item["knowledge_id"], "移出手册")
                + "</div></li>"
            )
        body += (
            '</ol><h2 id="booklet-add">查找并收录已保存教案</h2><p class="library-intro">只收录你已经确认保存的教案。草稿请先到知识资产中预览确认。</p><form class="library-search" method="get" action="'
            + url
            + '/edit#booklet-add"><label class="visually-hidden" for="lesson-query">查找教案标题、主题或正文</label><input id="lesson-query" name="q" maxlength="120" placeholder="查找教案标题、主题或正文" value="'
            + escape(q, quote=True)
            + '"><button class="button button-outline">查找教案</button></form><div class="booklet-list">'
        )
        if not candidates:
            body += "<p>没有找到已保存教案。可以换个关键词，或先在知识资产中确认保存草稿。</p>"
        for item in candidates[:20]:
            lesson_url = "/web/knowledge/" + item["knowledge_id"]
            if q:
                lesson_url += (
                    "?"
                    + urlencode(
                        {
                            "find": q,
                            "result_page": number,
                            "booklet": book["booklet_id"],
                        }
                    )
                    + "#lesson-find"
                )
            body += (
                '<article class="library-card"><h3><a href="'
                + escape(lesson_url, quote=True)
                + '">'
                + escape(item["title"])
                + "</a></h3><p>"
                + escape(item["topic"])
                + "</p>"
                + search_excerpt(item, q)
                + (
                    '<span class="library-badge">已在手册中</span>'
                    if item["knowledge_id"] in ids
                    else action("add", item["knowledge_id"], "收录到手册")
                )
                + "</article>"
            )
        body += '</div><nav class="library-paging" aria-label="可收录教案分页">'
        if number > 1:
            body += (
                '<a href="?'
                + urlencode({"q": q, "page": number - 1})
                + '#booklet-add">← 上一页教案</a>'
            )
        if len(candidates) > 20:
            body += (
                '<a href="?'
                + urlencode({"q": q, "page": number + 1})
                + '#booklet-add">下一页教案 →</a>'
            )
        return page("整理手册 · " + book["title"], body + "</nav>", code=code)

    @app.get("/web/booklets/{identity}/edit", include_in_schema=False)
    def edit(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            book = dialogue.booklet(account.user_id, identity, chapter=0)
            return (
                edit_page(request, account, book)
                if book
                else problem("找不到这本本人手册。", 404)
            )
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("暂时无法读取手册目录。", 503)

    @app.post("/web/booklets/{identity}/position", include_in_schema=False)
    async def remember_position(request: Request, identity: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(
            request, {"csrf", "revision", "knowledge_id", "position_revision"}
        )
        if (
            values is None
            or not re.fullmatch(r"[1-9][0-9]{0,9}", values["revision"])
            or not re.fullmatch(r"0|[1-9][0-9]{0,9}", values["position_revision"])
            or not re.fullmatch(r"[a-f0-9]{32}", values["knowledge_id"])
        ):
            return problem("续读页面无法核对，请重新打开手册。", 403)
        binding = (
            identity
            + "."
            + values["revision"]
            + "."
            + values["knowledge_id"]
            + "."
            + values["position_revision"]
        )
        if not valid(request, values, "position", binding):
            return problem("续读页面无法核对，请重新打开手册。", 403)
        try:
            result = await run_in_threadpool(
                dialogue.remember_booklet_position,
                account.user_id,
                identity,
                int(values["revision"]),
                values["knowledge_id"],
                int(values["position_revision"]),
            )
            if result == "missing":
                return problem("找不到这本本人手册。", 404)
            if result == "conflict":
                return problem(
                    "另一页面已经更新手册或续读位置。本次没有覆盖，请重新打开手册后选择。",
                    409,
                )
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("续读位置暂时无法保存，请稍后重新打开手册核对。", 503)
        return redirect("/web/booklets/" + identity + "#booklet-reading")

    @app.post("/web/booklets/{identity}/{operation}", include_in_schema=False)
    async def change(request: Request, identity: str, operation: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        if operation not in {"title", "add", "up", "down", "remove"}:
            return problem("找不到这项手册操作。", 404)
        expected = {
            "csrf",
            "revision",
            "q",
            "page",
            "title" if operation == "title" else "knowledge_id",
        }
        values = await fields(request, expected)
        if values is None or not re.fullmatch(r"[1-9][0-9]{0,9}", values["revision"]):
            return problem("手册页面无法核对，请重新打开。", 403)
        lesson = values.get("knowledge_id")
        binding = (
            identity
            + "."
            + values["revision"]
            + ("." + lesson if lesson is not None else "")
        )
        if (
            lesson is not None and re.fullmatch(r"[a-f0-9]{32}", lesson) is None
        ) or not valid(request, values, operation, binding):
            return problem("手册页面无法核对，请重新打开。", 403)
        try:
            q, number = query_values(values)
            request.state.booklet_search = (q, number)
            try:
                result = await run_in_threadpool(
                    dialogue.change_booklet,
                    account.user_id,
                    identity,
                    int(values["revision"]),
                    operation,
                    knowledge_id=lesson,
                    title=values.get("title"),
                )
            except ValueError as error:
                book = dialogue.booklet(account.user_id, identity, chapter=0)
                return (
                    edit_page(
                        request,
                        account,
                        book,
                        title=values.get("title"),
                        message=str(error),
                        code=400,
                    )
                    if book
                    else problem("找不到这本本人手册。", 404)
                )
            if result == "missing":
                return problem("找不到这本本人手册。", 404)
            if result == "conflict":
                book = dialogue.booklet(account.user_id, identity, chapter=0)
                return edit_page(
                    request,
                    account,
                    book,
                    title=values.get("title"),
                    message="另一页面已经更新手册。本次操作尚未保存，请核对当前目录后再操作。"
                    + ("填写的名称仍保留在下方。" if operation == "title" else ""),
                    code=409,
                )
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("手册暂时无法保存，请先查看当前目录。", 503)
        return redirect(
            "/web/booklets/"
            + identity
            + "/edit?"
            + urlencode({"q": q, "page": number})
            + ("#booklet-add" if operation == "add" else "")
        )

    def find_form(identity, query=""):
        return (
            '<form class="library-search" method="get" action="/web/booklets/'
            + identity
            + '/find"><label class="visually-hidden" for="booklet-find-query">在本手册内查找</label><input id="booklet-find-query" name="q" maxlength="120" placeholder="查找本册标题、主题或正文" value="'
            + escape(query, quote=True)
            + '"><button class="button button-outline" type="submit">查找章节</button></form>'
        )

    @app.get("/web/booklets/{identity}/find", include_in_schema=False)
    def find(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            if set(request.query_params) - {"q", "page"} or any(
                len(request.query_params.getlist(key)) > 1 for key in ("q", "page")
            ):
                raise ValueError("查找条件无法核对，请重新填写。")
            q, number = query_values(request.query_params)
            results = dialogue.find_booklet(account.user_id, identity, q, page=number)
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("暂时无法查找本手册，请稍后再试。", 503)
        if results is None:
            return problem("找不到这本本人手册。", 404)
        url = "/web/booklets/" + identity
        body = (
            '<p><a class="text-link" href="'
            + url
            + '">← 返回手册阅读</a></p><h2>'
            + escape(results["title"])
            + '</h2><p class="library-intro">只查这本手册已收录且可用教案的当前标题、主题与正文；引用和其他教案不在范围内。每页最多20章，按手册顺序展示。查找与阅读不调用AI，也不改写续读位置。</p>'
            + find_form(identity, q)
        )
        if q:
            body += (
                "<h2>找到 "
                + str(results["total"])
                + " 个章节 · 第 "
                + str(number)
                + " 页</h2>"
            )
            for item in results["items"]:
                target = (
                    url
                    + "?"
                    + urlencode(
                        {"lesson": item["knowledge_id"], "find": q, "find_page": number}
                    )
                    + "#booklet-reading"
                )
                body += (
                    '<article class="library-card"><p class="lesson-search-label">第 '
                    + str(item["number"])
                    + " 章 · 教案第 "
                    + str(item["revision"])
                    + " 版</p><h3>"
                    + escape(item["title"])
                    + "</h3>"
                    + search_excerpt(item, q)
                    + '<a class="text-link" href="'
                    + escape(target, quote=True)
                    + '">打开匹配章节 →</a></article>'
                )
            if not results["items"]:
                body += '<p class="library-empty">这一页没有匹配章节，可以缩短关键词或返回上一页。</p>'
            body += '<nav class="library-paging" aria-label="手册查找翻页">'
            for target, label, visible in (
                (number - 1, "← 上一页", number > 1),
                (number + 1, "下一页 →", number * 20 < results["total"]),
            ):
                if visible:
                    body += (
                        '<a href="'
                        + escape(
                            url + "/find?" + urlencode({"q": q, "page": target}),
                            quote=True,
                        )
                        + '">'
                        + label
                        + "</a>"
                    )
            body += "</nav>"
        else:
            body += '<p class="library-empty">输入关键词，开始查找这本手册。按原文字词匹配，英文字母不区分大小写。</p>'
        return page("手册内查找", body)

    @app.get("/web/booklets/{identity}", include_in_schema=False)
    def read(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            if any(
                len(request.query_params.getlist(key)) > 1
                for key in ("chapter", "lesson", "find", "find_page")
            ):
                raise ValueError("章节或查找条件重复，请重新打开。")
            q = search_query(request.query_params.get("find", ""))
            find_page = request.query_params.get("find_page", "1")
            if not re.fullmatch(r"[1-9][0-9]{0,3}|10000", find_page):
                raise ValueError("查找结果页码无法核对。")
            lesson = request.query_params.get("lesson")
            if lesson is not None and (
                re.fullmatch(r"[a-f0-9]{32}", lesson) is None
                or "chapter" in request.query_params
            ):
                raise ValueError("请只选择一个有效章节。")
        except ValueError as error:
            return problem(str(error))
        try:
            value = request.query_params.get("chapter")
            if value is not None and not re.fullmatch(r"[1-9][0-9]{0,2}", value):
                return problem("请检查章节编号。", 404)
            book = dialogue.booklet(
                account.user_id,
                identity,
                chapter=lesson or (int(value) if value is not None else "resume"),
            )
            if book is None:
                return problem("找不到这本本人手册。", 404)
            number = book["selected_chapter"]
            if book["chapters"] and number > len(book["chapters"]):
                return problem("找不到这个手册章节。", 404)
        except LookupError:
            target = (
                "/web/booklets/"
                + identity
                + "/find?"
                + urlencode({"q": q, "page": find_page})
            )
            return page(
                "章节已变化",
                '<p>这份教案已不在本手册目录中，请重新查找。</p><a class="text-link" href="'
                + escape(target, quote=True)
                + '">返回本册查找结果</a>',
                code=404,
            )
        except (sqlite3.Error, ValueError):
            return problem("暂时无法读取手册。", 503)
        url = "/web/booklets/" + identity

        def chapter_link(target):
            args = {"chapter": target}
            if q and book["chapters"]:
                args = {
                    "lesson": book["chapters"][target - 1]["knowledge_id"],
                    "find": q,
                    "find_page": find_page,
                }
            return "?" + urlencode(args) + "#booklet-reading"

        body = (
            '<p class="library-intro">共 '
            + str(len(book["chapters"]))
            + ' 章。阅读使用已保存教案的最新版，导出保留下载时的版本。阅读和整理目录不调用 AI。</p><div class="library-actions"><a class="button button-outline" href="'
            + url
            + '/edit">收录教案与整理目录</a><a class="button button-outline" href="'
            + url
            + '/download?format=html">导出整册阅读版</a><a class="text-link" href="'
            + url
            + '/download?format=md">导出整册 Markdown</a><a class="text-link" href="'
            + url
            + escape(chapter_link(1), quote=True)
            + '">从头阅读</a></div>'
            + find_form(identity, q)
            + (
                '<p><a class="text-link" href="'
                + escape(
                    url + "/find?" + urlencode({"q": q, "page": find_page}), quote=True
                )
                + '">← 返回本册查找结果</a></p>'
                if q
                else ""
            )
            + '<p class="lesson-revision-note">'
            + escape(booklet_position_text(book))
            + ' 阅读位置不代表学习完成或掌握程度。</p><details class="library-card booklet-toc" open><summary>手册目录</summary><ol>'
        )
        for item in book["chapters"]:
            body += (
                "<li><a"
                + (' aria-current="page"' if item["number"] == number else "")
                + ' href="'
                + escape(chapter_link(item["number"]), quote=True)
                + '">'
                + escape(item["title"])
                + "</a></li>"
            )
        body += "</ol></details>"
        if not book["chapters"]:
            body += '<section class="library-card"><h2>从第一章开始</h2><p>这本手册还没有收录教案，点击上方“收录教案与整理目录”开始整理。</p></section>'
        else:
            item = book["chapters"][number - 1]
            body += (
                '<article id="booklet-reading" class="library-card"><p class="eyebrow">第 '
                + str(number)
                + " 章 / 共 "
                + str(len(book["chapters"]))
                + " 章</p><h2>"
                + escape(item["title"])
                + "</h2>"
            )
            if q:
                body += (
                    '<p><a class="text-link" href="'
                    + escape(
                        url + "/find?" + urlencode({"q": q, "page": find_page}),
                        quote=True,
                    )
                    + '">← 返回本册查找结果</a></p>'
                )
            if item.get("missing"):
                body += "<p>原教案暂不可用，请回目录核对；系统不会改用其他教案。</p>"
            else:
                if q:
                    match = lesson_match(
                        item["title"], item["topic"], item["content"], q
                    )
                    body += (
                        search_excerpt({"search_match": match}, q)
                        if match["fields"]
                        else '<p class="lesson-search-label">本章内容可能已更新，当前未匹配关键词；可返回结果重新查找。</p>'
                    )
                position = book["reading_position"]
                current = position["knowledge_id"] == item["knowledge_id"]
                binding = (
                    identity
                    + "."
                    + str(book["revision"])
                    + "."
                    + item["knowledge_id"]
                    + "."
                    + str(position["revision"])
                )
                body += (
                    '<div class="library-actions"><form method="post" action="'
                    + url
                    + '/position">'
                    + hidden(request, "position", binding)
                    + '<input type="hidden" name="revision" value="'
                    + str(book["revision"])
                    + '">'
                    + '<input type="hidden" name="knowledge_id" value="'
                    + item["knowledge_id"]
                    + '">'
                    + '<input type="hidden" name="position_revision" value="'
                    + str(position["revision"])
                    + '">'
                    + (
                        '<span class="library-badge">已记住本章位置</span>'
                        if current
                        else '<button class="button button-outline" type="submit">记住本章位置</button>'
                    )
                    + '</form><span class="lesson-revision-note">下次打开从记住的章节继续；仅浏览不会改写位置。</span></div>'
                )
                body += (
                    '<p class="lesson-revision-note">当前教案 · 第 '
                    + str(item["revision"])
                    + ' 版</p><div class="library-actions"><a class="text-link" href="/web/knowledge/'
                    + item["knowledge_id"]
                    + '">打开原教案与版本 →</a><form method="post" action="/web/knowledge/'
                    + item["knowledge_id"]
                    + '/review"><input type="hidden" name="csrf" value="'
                    + library_csrf(
                        csrf_key,
                        request.cookies.get("coach_login_session", ""),
                        "review",
                        item["knowledge_id"],
                    )
                    + '"><button class="button button-outline" type="submit">在对话中重温本章</button></form></div>'
                )
                if item.get("unit_summary"):
                    body += (
                        '<details class="book-study-summary"><summary>本章生成时的整理范围</summary><p>'
                        + escape(unit_scope_text(item["unit_summary"])).replace(
                            "\n", "<br>"
                        )
                        + "</p></details>"
                    )
                body += (
                    '<div class="lesson-document markdown-content">'
                    + coach_markdown(item["content"])
                    + "</div>"
                )
                for source in item["citations"]:
                    body += (
                        '<details class="citation"><summary>整理时参考：'
                        + escape(source["title"] + " · " + source["locator"])
                        + "</summary><p>"
                        + escape(source["excerpt"])
                        + "</p></details>"
                    )
            body += '</article><nav class="library-paging" aria-label="手册章节切换">'
            if number > 1:
                body += (
                    '<a href="'
                    + escape(chapter_link(number - 1), quote=True)
                    + '">← 上一章</a>'
                )
            if number < len(book["chapters"]):
                body += (
                    '<a href="'
                    + escape(chapter_link(number + 1), quote=True)
                    + '">下一章 →</a>'
                )
            body += "</nav>"
        return page(book["title"], body)

    @app.get("/web/booklets/{identity}/download", include_in_schema=False)
    def download(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        format = request.query_params.get("format", "html")
        if format not in {"html", "md"}:
            return problem("请选择阅读版或 Markdown 格式。")
        try:
            book = dialogue.booklet(account.user_id, identity)
            if book is None:
                return problem("找不到这本本人手册。", 404)
            content = (
                booklet_document(book) if format == "html" else booklet_markdown(book)
            )
        except (sqlite3.Error, ValueError):
            return problem("手册暂时无法导出。", 503)
        headers = {
            **HEADERS,
            "Content-Disposition": "attachment; filename=learning-booklet."
            + format
            + "; filename*=UTF-8''"
            + quote(book["title"] + "." + format, safe=""),
        }
        return Response(
            content,
            media_type="text/html" if format == "html" else "text/markdown",
            headers=headers,
        )
