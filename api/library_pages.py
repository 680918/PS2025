"""Account-owned materials and explicit lesson approval. No AI calls in these routes."""

import hashlib
import hmac
import re
import secrets
import sqlite3
from datetime import datetime, timezone, timedelta
from html import escape
from threading import BoundedSemaphore, Lock
from urllib.parse import parse_qs, quote, urlencode

from fastapi import Request
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    Response,
    JSONResponse,
    StreamingResponse,
)
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask
from api.asset_export import build_export, export_summary, ExportError, SCOPES, PERIODS
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartParser, MultiPartException
from api.coach_markdown import coach_markdown

from api.public_pages import _render_layout
from coach.materials import MaterialError, MAX_FILE_BYTES
from coach.book_study import study_directory, unit_chunks
from coach.unit_lessons import unit_lesson_plan, send_unit_lesson, unit_scope_text
from coach.knowledge_search import search_query, literal_ranges, match_contexts
import json
from uuid import uuid4
from coach.learning_topics import (
    discussion_material,
    select_discussion_material,
    TopicBusy,
)
from security.login_sessions import signed_in_account
from security.registration_rate_limit import RegistrationRateLimiter


HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Content-Security-Policy": "default-src 'none'; style-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
}


def library_csrf(key, token, purpose, identity=""):
    return hmac.new(
        key, f"library.{purpose}.{identity}.{token}".encode("utf-8"), hashlib.sha256
    ).hexdigest()


def lesson_html(content):
    return coach_markdown(content)


def search_highlight(text, query):
    parts, cursor = [], 0
    for start, end in literal_ranges(text, query):
        parts.extend(
            (escape(text[cursor:start]), "<mark>" + escape(text[start:end]) + "</mark>")
        )
        cursor = end
    parts.append(escape(text[cursor:]))
    return "".join(parts)


def search_excerpt(item, query):
    match = item.get("search_match")
    if not query or match is None:
        return ""
    excerpt = match["excerpt"]
    if excerpt is None:
        return (
            '<p class="lesson-search-label">匹配：'
            + escape("、".join(match["fields"]))
            + "</p>"
        )
    return (
        '<div class="lesson-search-result"><p class="lesson-search-label">匹配：'
        + escape("、".join(match["fields"]))
        + '</p><p class="lesson-search-excerpt">'
        + ("…" if excerpt["before"] else "")
        + search_highlight(excerpt["text"], query)
        + ("…" if excerpt["after"] else "")
        + "</p></div>"
    )


def register_library_pages(
    app,
    accounts,
    materials,
    dialogue,
    *,
    csrf_key,
    summary_responder=None,
    summary_slots=None,
    summary_limit=None,
):
    summary_slots = summary_slots or BoundedSemaphore(2)
    summary_limit = summary_limit or RegistrationRateLimiter(
        per_client_limit=8, total_limit=80
    )
    view_limit = RegistrationRateLimiter(per_client_limit=60, total_limit=600)
    write_limit = RegistrationRateLimiter(per_client_limit=12, total_limit=60)
    upload_slots = BoundedSemaphore(2)
    export_slots = BoundedSemaphore(2)
    export_limit = RegistrationRateLimiter(per_client_limit=2, total_limit=10)

    def page(title, content, *, code=200, interactive=False):
        body = (
            '<main id="main-content" class="library-space"><nav class="library-tabs" aria-label="工作区入口"><a href="/web/welcome">← 回到对话</a><a href="/web/studies">我的学习</a><a href="/web/materials">资料与书籍</a><a href="/web/knowledge">知识资产沉淀</a><a href="/web/memories">我的学习记忆</a><a href="/web/export">导出学习资料</a></nav><h1>'
            + escape(title)
            + "</h1>"
            + content
            + "</main>"
        )
        return HTMLResponse(
            _render_layout(title + " · 知行", body, signed_in=True),
            status_code=code,
            headers={
                **HEADERS,
                "Content-Security-Policy": "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            }
            if interactive
            else HEADERS,
        )

    def problem(message, code=400):
        return page(
            "操作暂未完成",
            '<p class="form-error-summary" role="alert">'
            + escape(message)
            + '</p><a class="button button-outline" href="/web/materials">返回资料与书籍</a><a class="button button-outline" href="/web/knowledge">返回知识库</a>',
            code=code,
        )

    def redirect(url):
        return RedirectResponse(url, status_code=303, headers=HEADERS)

    def auth(request, *, write=False):
        wait = (write_limit if write else view_limit).admit(
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
            return None, problem("暂时无法读取登录状态。", 503)
        return (account, None) if account else (None, redirect("/web/login"))

    def csrf(request, purpose, identity=""):
        return library_csrf(
            csrf_key, request.cookies.get("coach_login_session", ""), purpose, identity
        )

    def input_csrf(request, purpose, identity=""):
        return (
            '<input type="hidden" name="csrf" value="'
            + csrf(request, purpose, identity)
            + '">'
        )

    def action(request, url, purpose, identity, label):
        return (
            '<form method="post" action="'
            + url
            + '">'
            + input_csrf(request, purpose, identity)
            + '<button class="button button-outline" type="submit">'
            + escape(label)
            + "</button></form>"
        )

    def origin_ok(request):
        return request.headers.get(
            "sec-fetch-site"
        ) != "cross-site" and request.headers.get("origin") in {
            None,
            "null",
            f"{request.url.scheme}://{request.url.netloc}",
        }

    async def fields(request, expected, *, limit=512000):
        if (
            request.headers.get("content-type", "").split(";", 1)[0]
            != "application/x-www-form-urlencoded"
        ):
            return None
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > limit:
                return None
            body.extend(chunk)
        try:
            values = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=len(expected),
                errors="strict",
            )
        except (ValueError, UnicodeError):
            return None
        if set(values) != expected or any(len(value) != 1 for value in values.values()):
            return None
        return {key: value[0] for key, value in values.items()}

    def valid_csrf(request, values, purpose, identity=""):
        return (
            values is not None
            and origin_ok(request)
            and bool(re.fullmatch(r"[a-f0-9]{64}", values.get("csrf", "")))
            and secrets.compare_digest(values["csrf"], csrf(request, purpose, identity))
        )

    def export_problem(request, message, code=400, retry=None):
        result = (
            JSONResponse({"error": message}, status_code=code, headers=HEADERS)
            if request.headers.get("accept") == "application/json"
            else page(
                "导出暂未完成",
                '<p class="form-error-summary" role="alert">'
                + escape(message)
                + '</p><a class="button button-outline" href="/web/export">返回选择导出内容</a>',
                code=code,
            )
        )
        if retry:
            result.headers["Retry-After"] = str(retry)
        return result

    @app.get("/web/export", include_in_schema=False)
    def export_page(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            summary = export_summary(
                dialogue.database_path, materials.database_path, account.user_id
            )
        except (sqlite3.Error, OSError):
            return export_problem(request, "暂时无法读取导出目录，请稍后重试。", 503)
        options = ""
        material_bytes = summary["material_bytes"]
        material_size = (
            f"{material_bytes / 1024**2:.1f} MB"
            if material_bytes >= 1024**2
            else f"{material_bytes / 1024:.1f} KB"
            if material_bytes >= 1024
            else f"{material_bytes} 字节"
        )
        descriptions = {
            "saved": "已经由你确认保存的教案，包含阅读版、Markdown 文本与引用说明。",
            "booklets": "你组织的学习手册，按目录收录当前教案版本，包含整册阅读版和 Markdown。",
            "memories": "你明确保存的学习目标、基础和偏好，包含阅读版与文本。",
            "drafts": "尚未确认的教案草稿；导出后仍保留草稿状态。",
            "chat": "你的提问、教练回复、实际引用说明，以及各主题学习位置、书籍学习目录与讲解记录。",
            "materials": f"你上传或粘贴的原始内容，合计约 {material_size}。",
        }
        for scope, label in SCOPES.items():
            count = summary[scope]
            disabled = (
                " disabled"
                if not count and not (scope == "chat" and summary["learning"])
                else ""
            )
            checked = " checked" if scope in {"saved", "booklets"} and count else ""
            options += (
                '<label class="export-option"><input type="checkbox" name="scope" value="'
                + scope
                + '"'
                + checked
                + disabled
                + "><span><strong>"
                + label
                + " · "
                + str(count)
                + (" 轮" if scope == "chat" else " 份")
                + "</strong><span>"
                + descriptions[scope]
                + "</span></span></label>"
            )
        content = (
            '<p class="library-intro">把学习积累下载一份到自己的电脑。Coach 内的内容继续保留，不会删除，也不会调用 AI。</p>'
            '<section class="library-card export-card"><form id="asset-export-form" method="post" action="/web/export">'
            + input_csrf(request, "export")
            + "<fieldset><legend>选择导出的内容</legend>"
            + options
            + '</fieldset><div class="export-period"><label for="export-period">聊天记录时间范围</label><select id="export-period" name="period"><option value="all">全部时间</option><option value="30">最近 30 天</option><option value="90">最近 90 天</option></select><p class="export-note">只影响聊天记录；教案、资料、学习记忆和各主题学习位置不受此选项影响。</p></div>'
            '<p class="export-note">下载 ZIP 压缩包后，请先完整解压，再打开“打开这里.html”。资料较多时可按类型分别导出，单次内容上限 100 MB。</p>'
            '<button class="button button-primary" type="submit">下载所选学习资料</button><p id="asset-export-status" role="status" aria-live="polite"></p></form></section>'
            '<p class="library-intro">下载的是当前内容副本。本地修改不会自动同步到 Coach；账户恢复和整库备份会在后续单独提供。</p><script src="/static/asset-export.js" defer></script>'
        )
        return page("导出我的学习资料", content, interactive=True)

    @app.post("/web/export", include_in_schema=False)
    async def export_download(request: Request):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        if not origin_ok(request):
            return export_problem(request, "页面无法核对，请刷新导出页面后重试。", 403)
        if (
            request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
            != "application/x-www-form-urlencoded"
        ):
            return export_problem(request, "无法读取导出选项。")
        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > 4096:
                return export_problem(request, "导出选项过长。")
            body.extend(chunk)
        try:
            values = parse_qs(
                body.decode("ascii"),
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=len(SCOPES) + 2,
                encoding="utf-8",
                errors="strict",
            )
            if (
                not {"csrf", "period"} <= values.keys()
                or not values.keys() <= {"csrf", "period", "scope"}
                or len(values["csrf"]) != 1
                or len(values["period"]) != 1
            ):
                raise ValueError
            if not valid_csrf(request, {"csrf": values["csrf"][0]}, "export"):
                return export_problem(
                    request, "页面无法核对，请刷新导出页面后重试。", 403
                )
            scopes, period = values.get("scope", []), values["period"][0]
            if (
                not scopes
                or len(scopes) != len(set(scopes))
                or not set(scopes) <= SCOPES.keys()
                or period not in PERIODS
            ):
                return export_problem(
                    request, "请选择需要导出的内容，并检查聊天时间范围。"
                )
        except (UnicodeError, ValueError):
            return export_problem(request, "无法读取导出选项，请刷新页面后重新选择。")
        wait = export_limit.admit(account.user_id)
        if wait:
            return export_problem(
                request, f"导出较频繁，请 {wait} 秒后重试。", 429, wait
            )
        if not export_slots.acquire(blocking=False):
            return export_problem(request, "当前有资料包正在整理，请稍后重试。", 503)
        try:
            archive = await run_in_threadpool(
                build_export,
                dialogue.database_path,
                materials.database_path,
                account.user_id,
                scopes,
                period=period,
            )
        except ExportError as error:
            export_slots.release()
            return export_problem(request, str(error))
        except (sqlite3.Error, OSError, ValueError):
            export_slots.release()
            return export_problem(request, "资料包暂时无法生成，请稍后重试。", 503)
        except BaseException:
            export_slots.release()
            raise
        cleanup_lock = Lock()
        cleaned = False

        def cleanup():
            nonlocal cleaned
            with cleanup_lock:
                if not cleaned:
                    cleaned = True
                    try:
                        archive.close()
                    finally:
                        export_slots.release()

        def stream():
            try:
                yield from archive.chunks()
            finally:
                cleanup()

        return StreamingResponse(
            stream(),
            media_type="application/zip",
            headers={
                **HEADERS,
                "Content-Length": str(archive.size),
                "Content-Disposition": "attachment; filename=coach-learning-export.zip; filename*=UTF-8''"
                + quote(archive.filename, safe=""),
            },
            background=BackgroundTask(cleanup),
        )

    def material_find_values(request, *, preview=False):
        names = (
            ("find", "find_material", "find_page")
            if preview
            else ("q", "material", "page")
        )
        if any(len(request.query_params.getlist(name)) > 1 for name in names):
            raise ValueError("查找条件重复，请重新输入。")
        query = search_query(request.query_params.get(names[0], ""))
        scope = request.query_params.get(names[1], "")
        number = request.query_params.get(names[2], "1")
        if not re.fullmatch(r"[1-9][0-9]{0,4}", number) or int(number) > 10000:
            raise ValueError("请输入有效的查找结果页码。")
        if scope and not re.fullmatch(r"[a-f0-9]{32}", scope):
            raise ValueError("查找范围无法读取。")
        return query, scope, int(number)

    def material_search_form(items, *, query="", scope=""):
        options = '<option value="">全部资料</option>'
        for item in items:
            options += (
                '<option value="'
                + item["material_id"]
                + '"'
                + (" selected" if item["material_id"] == scope else "")
                + ">"
                + escape(item["title"])
                + "</option>"
            )
        return (
            '<form class="material-search-form library-card" method="get" action="/web/materials/find">'
            '<div><label for="material-query">查找资料原文</label><input id="material-query" name="q" maxlength="120" required value="'
            + escape(query, quote=True)
            + '" placeholder="输入关键词或一句原文"></div><div><label for="material-scope">查找范围</label><select id="material-scope" name="material">'
            + options
            + '</select></div><button class="button button-primary" type="submit">查找原文</button></form>'
        )

    @app.get("/web/materials/find", include_in_schema=False)
    def find_materials(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            query, scope, number = material_find_values(request)
            items = materials.list(account.user_id)
            if scope and not any(item["material_id"] == scope for item in items):
                return problem("找不到这份可读取资料。", 404)
            results = materials.find_chunks(
                account.user_id, query, material_id=scope or None, page=number
            )
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("资料暂时无法查找，请稍后再试。", 503)
        cards = []
        for item in results[:20]:
            link = (
                "/web/materials/"
                + item["material_id"]
                + "?"
                + urlencode(
                    {
                        "part": item["chunk_index"],
                        "find": query,
                        "find_material": scope,
                        "find_page": number,
                    }
                )
                + "#material-find"
            )
            cards.append(
                '<article class="library-item material-search-result"><h2>'
                + escape(item["title"])
                + "</h2><p>"
                + escape(item["locator"])
                + "</p>"
                + search_excerpt(item, query)
                + '<a class="text-link material-hit" href="'
                + escape(link, quote=True)
                + '">查看原文并选段学习 →</a></article>'
            )
        paging = ""
        for target, label, visible in (
            (number - 1, "← 上一页", number > 1),
            (number + 1, "下一页 →", len(results) > 20 and number < 10000),
        ):
            if visible:
                link = "/web/materials/find?" + urlencode(
                    {"q": query, "material": scope, "page": target}
                )
                paging += '<a href="' + escape(link, quote=True) + '">' + label + "</a>"
        body = (
            '<p class="library-intro">从原文找到依据，再带着具体片段去学习。</p>'
            + material_search_form(items, query=query, scope=scope)
            + '<p class="lesson-search-label">按输入文字逐字查找已提取原文，英文不区分大小写。每页最多 20 个匹配片段；相邻片段可能包含重复原文。PDF 断行可能影响匹配，扫描图片尚不可查找。查找和阅读不调用 AI，也不改变学习位置。</p>'
        )
        if query:
            body += (
                '<h2 class="material-results-title">“'
                + escape(query)
                + "” · 第 "
                + str(number)
                + " 页</h2>"
            )
        body += (
            '<div class="library-list">'
            + (
                "".join(cards)
                or '<p class="library-empty">'
                + (
                    "没有找到匹配原文。试试更短的关键词，或更换查找范围。"
                    if query
                    else "输入一个关键词，开始查找你的资料。"
                )
                + "</p>"
            )
            + '</div><nav class="library-paging" aria-label="原文查找结果翻页">'
            + paging
            + "</nav>"
        )
        body += '<p><a class="text-link" href="/web/materials">返回资料与书籍 →</a></p>'
        return page("查找资料原文", body)

    @app.get("/web/materials", response_class=HTMLResponse, include_in_schema=False)
    def list_materials(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            selected, items = (
                discussion_material(dialogue, materials, account.user_id),
                materials.list(account.user_id),
            )
        except sqlite3.Error:
            return problem("暂时无法读取资料。", 503)
        cards = []
        for item in items:
            identity = item["material_id"]
            label = (
                '<span class="library-badge">当前参与讨论</span>'
                if selected and selected["material_id"] == identity
                else ""
            )
            cards.append(
                '<article class="library-item"><h2><a href="/web/materials/'
                + identity
                + '">'
                + escape(item["title"])
                + "</a></h2>"
                + label
                + "<p>"
                + escape(item["filename"])
                + f' · {item["char_count"]} 字</p><div class="library-actions"><a class="text-link" href="/web/materials/{identity}">预览文字</a><a class="text-link" href="/web/materials/{identity}/plan">学习目录</a>'
                + action(
                    request,
                    f"/web/materials/{identity}/select",
                    "select",
                    identity,
                    "围绕这份资料讨论",
                )
                + "</div></article>"
            )
        clear = (
            action(request, "/web/materials/clear", "clear", "", "取消当前资料")
            if selected
            else ""
        )
        upload = (
            '<section id="add-material" class="library-card"><h2>添加一份资料</h2><p>文字型 PDF、TXT、Markdown；每份最多 10 MB，PDF 最多 500 页。扫描图片识别稍后接入。</p><form method="post" action="/web/materials/upload" enctype="multipart/form-data">'
            + input_csrf(request, "upload")
            + '<label for="material-title">资料名称（可选）</label><input id="material-title" name="title" maxlength="120"><label for="material-file">选择文件</label><input id="material-file" name="file" type="file" accept=".pdf,.txt,.md" required><button class="button button-primary" type="submit">上传并保存资料</button></form></section>'
        )
        paste = (
            '<section class="library-card"><h2>也可以粘贴文字</h2><form method="post" action="/web/materials/paste">'
            + input_csrf(request, "paste")
            + '<label for="paste-title">文字资料名称</label><input id="paste-title" name="title" maxlength="120" required><label for="paste-content">资料内容</label><textarea id="paste-content" name="content" rows="8" maxlength="50000" required></textarea><button class="button button-primary" type="submit">保存文字资料</button></form></section>'
        )
        return page(
            "资料与书籍",
            '<p class="library-intro">原始资料留在这里。选择一份资料后，回到同一个聊天框讨论。资料在本机保存；提问时，相关片段会交给你启用的 AI。</p>'
            + material_search_form(items)
            + clear
            + '<div class="library-list">'
            + (
                "".join(cards)
                or '<p class="library-empty">还没有资料。可以上传文件，或粘贴一段想学习的文字。</p>'
            )
            + '</div><div class="library-add-grid">'
            + upload
            + paste
            + "</div>",
        )

    @app.post(
        "/web/materials/upload", response_class=HTMLResponse, include_in_schema=False
    )
    async def upload(request: Request):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        if not origin_ok(request):
            return problem("页面无法核对，请返回资料页重试。", 403)
        if not upload_slots.acquire(blocking=False):
            return problem("还有资料正在处理，请稍后重试。", 503)
        form = None
        try:

            async def stream():
                total = 0
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > MAX_FILE_BYTES + 16384:
                        raise MultiPartException("size")
                    yield chunk

            form = await MultiPartParser(
                request.headers, stream(), max_files=1, max_fields=2, max_part_size=4096
            ).parse()
            if (
                len(form.multi_items()) != 3
                or set(form) != {"csrf", "title", "file"}
                or not isinstance(form["file"], UploadFile)
                or not isinstance(form["title"], str)
                or not isinstance(form["csrf"], str)
            ):
                return problem("上传内容无法读取，请重新选择文件。")
            if not valid_csrf(request, form, "upload"):
                return problem("页面无法核对，请返回资料页重试。", 403)
            raw = await form["file"].read(MAX_FILE_BYTES + 1)
            identity = await run_in_threadpool(
                materials.add,
                account.user_id,
                form["file"].filename or "",
                raw,
                title=form["title"],
            )
            return redirect("/web/materials/" + identity)
        except MaterialError as error:
            return problem(str(error))
        except (MultiPartException, UnicodeError, ValueError):
            return problem("上传格式无法读取，或文件超过 10 MB。")
        except (OSError, sqlite3.Error):
            return problem("资料暂时无法保存，请稍后重试。", 503)
        finally:
            if form is not None:
                await form.close()
            upload_slots.release()

    @app.post("/web/materials/paste", include_in_schema=False)
    async def paste(request: Request):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf", "title", "content"})
        if not valid_csrf(request, values, "paste"):
            return problem("页面无法核对或内容过长，请返回资料页重试。", 403)
        try:
            identity = await run_in_threadpool(
                materials.add,
                account.user_id,
                "粘贴资料.txt",
                values["content"].encode("utf-8"),
                title=values["title"],
                pasted=True,
            )
            return redirect("/web/materials/" + identity)
        except MaterialError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("文字资料暂时无法保存。", 503)

    def book_state(user_id, item, chunks):
        stored = dialogue.book_position(user_id, item["material_id"])
        return study_directory(
            item,
            chunks,
            dialogue.book_units(user_id, item["material_id"]),
            dialogue.book_coverage(user_id, item["material_id"]),
            stored["chunk_id"] if stored else None,
        )

    def select_part_button(request, identity, chunk, label):
        return (
            '<form method="post" action="/web/materials/'
            + identity
            + '/study">'
            + input_csrf(request, "study-part", identity + "." + chunk["chunk_id"])
            + '<input type="hidden" name="chunk_id" value="'
            + chunk["chunk_id"]
            + '"><button class="button button-primary" type="submit">'
            + escape(label)
            + "</button></form>"
        )

    def book_unit_editor(request, item, unit, values=None, *, message="", code=200):
        values = values or unit
        identity, unit_id = item["material_id"], unit["unit_id"]
        label = "PDF 文件页码" if item["kind"] == "pdf" else "文字片段编号"
        body = (
            '<p class="library-intro">'
            + escape(item["title"])
            + " · 按原文范围组织学习，不调用 AI。标题可使用原书章名，也可按自己的目标命名。</p>"
        )
        if message:
            body += (
                '<p class="form-error-summary" role="alert">' + escape(message) + "</p>"
            )
        body += (
            '<section class="library-card book-unit-editor"><form method="post" action="/web/materials/'
            + identity
            + "/plan/"
            + unit_id
            + '">'
            + input_csrf(
                request,
                "book-unit",
                identity + "." + unit_id + "." + str(unit["revision"]),
            )
            + '<input type="hidden" name="revision" value="'
            + str(unit["revision"])
            + '"><label for="unit-title">学习单元名称</label><input id="unit-title" name="title" maxlength="80" required value="'
            + escape(str(values["title"]), quote=True)
            + '"><div class="book-unit-range"><div><label for="unit-start">起始'
            + label
            + '</label><input id="unit-start" name="start_pos" type="number" min="1" required value="'
            + escape(str(values["start_pos"]), quote=True)
            + '"></div><div><label for="unit-end">结束'
            + label
            + '</label><input id="unit-end" name="end_pos" type="number" min="1" required value="'
            + escape(str(values["end_pos"]), quote=True)
            + '"></div></div><p class="lesson-revision-note">范围包含起止位置，单元之间不重叠，每份资料最多 60 个。PDF 使用文件实际页码，空白或无可提取文字的页面不会生成讲解片段。调整目录会按新范围重新计算已有讲解记录。</p><div class="library-actions"><button class="button button-primary" type="submit">'
            + ("核对后再次保存" if code == 409 else "保存学习单元")
            + '</button><a class="button button-outline" href="/web/materials/'
            + identity
            + '/plan">返回学习目录</a></div></form></section>'
        )
        return page(
            "修改学习单元" if unit["revision"] else "添加学习单元", body, code=code
        )

    @app.get("/web/materials/{identity}/plan", include_in_schema=False)
    def book_plan(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            item = materials.get(account.user_id, identity)
            chunks = materials.chunks(account.user_id, identity) if item else []
            if not item or not chunks:
                return problem("找不到这份可读取资料。", 404)
            state = book_state(account.user_id, item, chunks)
            stored = dialogue.book_position(account.user_id, identity)
            if stored and state["current"] is None:
                current_note = (
                    "原选段暂不可用；请从下方选择可读位置，系统不会自动换段。"
                )
            else:
                current_note = (
                    "上次位置 · " + state["current"]["locator"]
                    if state["current"]
                    else "选择一个位置，开始逐段学习。"
                )
            done = {
                row["chunk_id"]
                for row in dialogue.book_coverage(account.user_id, identity)
            }
            resume = state["current"] or next(
                (part for part in chunks if part["chunk_id"] not in done), chunks[0]
            )
            body = (
                '<p class="library-intro">按自己的节奏读书，把讨论逐渐沉淀为知识。</p><section class="library-card book-plan-overview"><p class="eyebrow">书籍学习</p><h2>'
                + escape(item["title"])
                + "</h2><p>可读内容已讲解 <strong>"
                + str(state["explained"])
                + " / "
                + str(state["total"])
                + '</strong> 段</p><progress max="'
                + str(state["total"])
                + '" value="'
                + str(state["explained"])
                + '" aria-label="可读片段讲解进度"></progress><p>'
                + escape(current_note)
                + '</p><p class="learning-record-note">仅记录成功取得且带原文引用的选段讲解，不代表已经掌握。浏览、目录编辑与选段不调用 AI；回到对话后点击讲解才调用。</p><div class="library-actions">'
                + select_part_button(
                    request,
                    identity,
                    resume,
                    "回到上次位置" if state["current"] else "开始逐段学习",
                )
                + '<a class="button button-outline" href="/web/materials/'
                + identity
                + '/plan/new">添加学习单元</a><a class="text-link" href="/web/materials/'
                + identity
                + '">查看原文与定位 →</a></div></section>'
            )
            if item["kind"] == "pdf" and item["readable_pages"] < item["page_count"]:
                body += '<p class="lesson-revision-note">部分 PDF 页没有可提取文字，进度仅涵盖可读片段；这不代表整本书已被完整处理。</p>'
            if request.query_params.get("notice") == "saved":
                body += '<p class="lesson-version-notice" role="status">学习单元已保存，已有讲解记录继续保留。</p>'
            body += '<h2>我的学习单元</h2><p class="library-intro">按起始位置排列。可按章节或自己的学习目标分组；没有分组的内容仍可在原文中选择学习。</p><div class="book-unit-list">'
            if not state["units"]:
                body += '<section class="library-card"><h3>先读起来，也可以慢慢整理目录</h3><p>你可以直接从第一段开始；需要时，再把原书章节或某个页码范围设为学习单元。</p></section>'
            for unit in state["units"]:
                selected = state["current"] if unit["current"] else unit["resume"]
                body += (
                    '<article class="library-card book-unit-card"><span class="library-badge">'
                    + ("当前位置" if unit["current"] else "学习单元")
                    + "</span><h3>"
                    + escape(unit["title"])
                    + "</h3><p>"
                    + escape(unit["label"])
                    + " · 已讲解 "
                    + str(unit["explained"])
                    + " / "
                    + str(unit["total"])
                    + ' 段</p><progress max="'
                    + str(max(1, unit["total"]))
                    + '" value="'
                    + str(unit["explained"])
                    + '" aria-label="本单元讲解进度"></progress><div class="library-actions">'
                    + (
                        select_part_button(
                            request,
                            identity,
                            selected,
                            "继续本单元" if unit["current"] else "进入本单元",
                        )
                        if selected
                        else "<p>原文暂不可用，请调整范围。</p>"
                    )
                    + '<a class="text-link" href="/web/materials/'
                    + identity
                    + "/plan/"
                    + unit["unit_id"]
                    + '">修改名称与范围</a></div><details class="book-unit-parts"><summary>查看本单元的原文位置与讲解记录</summary><ul>'
                )
                for part in unit["chunks"]:
                    body += (
                        '<li><a href="/web/materials/'
                        + identity
                        + "?part="
                        + str(part["chunk_index"])
                        + '">'
                        + escape(part["locator"])
                        + "</a><span>"
                        + ("已讲解" if part["chunk_id"] in done else "待讲解")
                        + "</span></li>"
                    )
                body += (
                    '</ul></details><p><a class="text-link" href="/web/materials/'
                    + identity
                    + "/plan/"
                    + unit["unit_id"]
                    + '/lessons">整理已讲解内容 · 查看本单元教案 →</a></p>'
                )
                related = dialogue.unit_knowledge(
                    account.user_id, identity, unit["unit_id"], limit=3
                )
                if related:
                    body += '<ul class="unit-lesson-links">'
                    for lesson in related:
                        body += (
                            '<li><a href="/web/knowledge/'
                            + lesson["knowledge_id"]
                            + '">'
                            + escape(lesson["title"])
                            + "</a> · "
                            + (
                                "已保存"
                                if lesson["status"] == "saved"
                                else "草稿待确认"
                            )
                            + "</li>"
                        )
                    body += "</ul>"
                body += "</article>"
            return page("书籍学习目录", body + "</div>")
        except (sqlite3.Error, ValueError):
            return problem("暂时无法读取学习目录，请稍后重试。", 503)

    def unit_summary_binding(identity, unit_id, values):
        return ".".join(
            (identity, unit_id, values["batch"], values["digest"], values["nonce"])
        )

    @app.get(
        "/web/materials/{identity}/plan/{unit_id}/lessons", include_in_schema=False
    )
    def unit_lessons_page(request: Request, identity: str, unit_id: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            plan = unit_lesson_plan(
                dialogue, materials, account.user_id, identity, unit_id
            )
            number = request.query_params.get("page", "1")
            if not re.fullmatch(r"[1-9][0-9]{0,5}", number):
                return problem("请检查教案目录页码。")
            number = int(number)
            lessons = dialogue.unit_knowledge(
                account.user_id, identity, unit_id, offset=(number - 1) * 20
            )
            recent = [
                (row, json.loads(row["scope_json"]))
                for row in dialogue.unit_knowledge(
                    account.user_id, identity, unit_id, limit=100
                )
            ]
            pending = any(
                turn["status"] == "pending"
                for turn in dialogue.view(account.user_id)["turns"]
            )
        except ValueError as error:
            return problem(str(error), 404)
        except sqlite3.Error:
            return problem("暂时无法读取单元教案。", 503)
        unit = plan["unit"]
        url = "/web/materials/" + identity + "/plan/" + unit_id + "/lessons"
        body = (
            '<p class="library-intro">'
            + escape(plan["material"]["title"])
            + " · "
            + escape(unit["title"])
            + '</p><a class="text-link" href="/web/materials/'
            + identity
            + '/plan">← 返回书籍学习目录</a><p><a class="text-link" href="#unit-lesson-assets">直接查看本单元教案 ↓</a></p><section class="library-card"><h2>把已讲解内容留成可重温的教案</h2><p>本单元已讲解 '
            + str(plan["explained"])
            + " / "
            + str(plan["total"])
            + " 段。仅整理下方列出的可读原文；未讲解部分不纳入本次草稿。每批最多 6 段，逐批由你决定是否整理，不会自动处理后续批次。</p><p>浏览不调用 AI；点击“整理本批教案草稿”会调用一次你启用的 AI。生成后可预览、修改并明确确认保存。</p></section>"
        )
        if not plan["batches"]:
            body += '<section class="library-card"><h2>先从一次讲解开始</h2><p>本单元还没有带原文引用的选段讲解记录。回到书籍学习目录进入本单元，点击讲解后，再来整理。</p></section>'
        if pending:
            body += '<p class="lesson-version-notice" role="status">教练正在回复，等本轮结束后刷新此页再整理。</p>'
        body += '<div class="book-unit-list">'
        for batch in plan["batches"]:
            source_ids = [source["source_id"] for source in batch["sources"]]
            existing = next(
                (
                    row
                    for row, scope in recent
                    if scope["unit_revision"] == unit["revision"]
                    and [source["chunk_id"] for source in scope["sources"]]
                    == source_ids
                ),
                None,
            )
            values = {
                "batch": str(batch["number"]),
                "digest": batch["digest"],
                "nonce": secrets.token_urlsafe(32),
            }
            body += (
                '<article class="library-card"><h2>第 '
                + str(batch["number"])
                + " / "
                + str(len(plan["batches"]))
                + " 批</h2><p>本批提供的原文位置：</p><ul>"
            )
            for source in batch["sources"]:
                body += "<li>" + escape(source["locator"]) + "</li>"
            body += "</ul>"
            if existing:
                body += (
                    '<p><a class="button button-primary" href="/web/knowledge/'
                    + existing["knowledge_id"]
                    + '">'
                    + (
                        "查看已有教案"
                        if existing["status"] == "saved"
                        else "查看待确认草稿"
                    )
                    + '</a></p><p class="learning-record-note">本批已有整理结果，可以先调阅。需要重新整理时再点击下方按钮，将再次调用 AI。</p>'
                )
            body += (
                '<form class="unit-summary-form" method="post" action="' + url + '">'
            )
            body += input_csrf(
                request, "unit-lesson", unit_summary_binding(identity, unit_id, values)
            )
            body += "".join(
                '<input type="hidden" name="' + key + '" value="' + value + '">'
                for key, value in values.items()
            )
            body += (
                '<button data-unit-submit class="button '
                + ("button-outline" if existing else "button-primary")
                + '" type="submit"'
                + (" disabled" if pending or summary_responder is None else "")
                + ">"
                + ("重新整理本批草稿" if existing else "整理本批教案草稿")
                + '</button><p class="unit-summary-wait" role="status" hidden><span class="waiting-dots" aria-hidden="true"><i></i><i></i><i></i></span>教练正在整理，请稍候；请勿重复提交。完成后会打开草稿预览。</p></form></article>'
            )
        body += '</div><h2 id="unit-lesson-assets">本单元的知识积累</h2><p class="library-intro">草稿与已保存教案集中在这里。教案保留生成时的范围说明，修订、版本、重温和导出继续使用原有功能。</p>'
        if summary_responder is None:
            body += '<p class="lesson-version-notice">当前未启用对话 AI，可先浏览已有教案，稍后启用再整理。</p>'
        if not lessons:
            body += "<p>这里暂时没有教案。</p>"
        for lesson in lessons[:20]:
            scope = json.loads(lesson["scope_json"])
            body += (
                '<article class="library-card"><span class="library-badge">'
                + ("已保存" if lesson["status"] == "saved" else "草稿待确认")
                + '</span><h3><a href="/web/knowledge/'
                + lesson["knowledge_id"]
                + '">'
                + escape(lesson["title"])
                + "</a></h3><p>生成时："
                + escape(scope["range"])
                + " · 第 "
                + str(scope["batch"])
                + " / "
                + str(scope["batch_count"])
                + ' 批</p><a class="text-link" href="/web/knowledge/'
                + lesson["knowledge_id"]
                + '">预览、保存与调阅 →</a></article>'
            )
        body += '<nav class="library-paging" aria-label="本单元教案分页">'
        if number > 1:
            body += '<a href="?page=' + str(number - 1) + '">← 上一页教案</a>'
        if len(lessons) > 20:
            body += '<a href="?page=' + str(number + 1) + '">下一页教案 →</a>'
        return page(
            "单元教案与整理",
            body + '</nav><script src="/static/unit-lessons.js" defer></script>',
            interactive=True,
        )

    @app.post(
        "/web/materials/{identity}/plan/{unit_id}/lessons", include_in_schema=False
    )
    async def generate_unit_lesson(request: Request, identity: str, unit_id: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf", "nonce", "batch", "digest"}, limit=4096)
        if (
            values is None
            or not re.fullmatch(r"[A-Za-z0-9_-]{43}", values["nonce"])
            or not re.fullmatch(r"[1-9][0-9]{0,3}", values["batch"])
            or not re.fullmatch(r"[a-f0-9]{64}", values["digest"])
            or not valid_csrf(
                request,
                values,
                "unit-lesson",
                unit_summary_binding(identity, unit_id, values),
            )
            or (
                request.headers.get("origin") == "null"
                and request.headers.get("sec-fetch-site") != "same-origin"
            )
        ):
            return problem("整理页面无法核对，请重新打开本单元的教案整理页面。", 403)
        if summary_responder is None:
            return problem("当前尚未启用对话 AI，请稍后再整理。", 503)
        wait = summary_limit.admit(request.client.host if request.client else "unknown")
        if wait:
            result = problem("整理较频繁，请稍后再试。", 429)
            result.headers["Retry-After"] = str(wait)
            return result
        if not summary_slots.acquire(blocking=False):
            return problem("教练正在处理其他请求，请稍后再试。", 409)
        try:
            outcome = await run_in_threadpool(
                send_unit_lesson,
                dialogue,
                materials,
                account.user_id,
                identity,
                unit_id,
                int(values["batch"]),
                values["digest"],
                values["nonce"],
                responder=summary_responder,
            )
            if outcome == "busy":
                return problem("教练还有回复未完成，请等本轮结束后再整理。", 409)
            result = dialogue.unit_lesson_result(account.user_id, values["nonce"])
            if result:
                return redirect("/web/knowledge/" + result)
            return page(
                "本次尚未形成教案草稿",
                '<p class="library-intro">本次未取得带完整选段引用的教案草稿，尚未保存。请先查看对话记录，再决定是否重新整理；系统不会自动重试。</p><a class="button button-outline" href="/web/materials/'
                + identity
                + "/plan/"
                + unit_id
                + '/lessons">返回单元整理</a><a class="text-link" href="/web/welcome">查看对话记录 →</a>',
                code=502,
            )
        except ValueError as error:
            return problem(str(error), 409)
        except sqlite3.Error:
            return problem(
                "整理结果暂时无法核对，请先查看本单元教案目录，避免重复提交。", 503
            )
        finally:
            summary_slots.release()

    @app.get("/web/materials/{identity}/plan/{unit_id}", include_in_schema=False)
    def edit_book_unit(request: Request, identity: str, unit_id: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            item = materials.get(account.user_id, identity)
            if not item:
                return problem("找不到这份资料。", 404)
            unit = next(
                (
                    unit
                    for unit in dialogue.book_units(account.user_id, identity)
                    if unit["unit_id"] == unit_id
                ),
                None,
            )
            if unit_id == "new":
                unit = {
                    "unit_id": uuid4().hex,
                    "revision": 0,
                    "title": "",
                    "start_pos": "",
                    "end_pos": "",
                }
            return (
                book_unit_editor(request, item, unit)
                if unit
                else problem("找不到这个学习单元。", 404)
            )
        except sqlite3.Error:
            return problem("暂时无法读取学习单元。", 503)

    @app.post("/web/materials/{identity}/plan/{unit_id}", include_in_schema=False)
    async def save_book_unit(request: Request, identity: str, unit_id: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(
            request, {"csrf", "revision", "title", "start_pos", "end_pos"}, limit=4096
        )
        if (
            values is None
            or not re.fullmatch(r"[a-f0-9]{32}", unit_id)
            or not re.fullmatch(r"(?:0|[1-9][0-9]{0,9})", values["revision"])
            or not valid_csrf(
                request,
                values,
                "book-unit",
                identity + "." + unit_id + "." + values["revision"],
            )
            or (
                request.headers.get("origin") == "null"
                and request.headers.get("sec-fetch-site") != "same-origin"
            )
        ):
            return problem("目录页面无法核对，请重新打开学习单元。", 403)
        try:
            item = materials.get(account.user_id, identity)
            chunks = materials.chunks(account.user_id, identity) if item else []
            if not item or not chunks:
                return problem("找不到这份可读取资料。", 404)
            revision = int(values["revision"])
            unit = {**values, "unit_id": unit_id, "revision": revision}
            try:
                if not all(
                    re.fullmatch(r"[1-9][0-9]{0,5}", values[key])
                    for key in ("start_pos", "end_pos")
                ):
                    raise ValueError("请输入有效的起止位置编号。")
                start, end = int(values["start_pos"]), int(values["end_pos"])
                if not unit_chunks(item, chunks, start, end):
                    raise ValueError(
                        "这个范围没有可提取文字，请换一个范围；不会自动改用其他页面。"
                    )
                result = await run_in_threadpool(
                    dialogue.save_book_unit,
                    account.user_id,
                    identity,
                    unit_id,
                    values["title"],
                    start,
                    end,
                    revision,
                )
            except (ValueError, TopicBusy) as error:
                return book_unit_editor(
                    request,
                    item,
                    unit,
                    values,
                    message=str(error),
                    code=409 if isinstance(error, TopicBusy) else 400,
                )
            if result == "missing":
                return problem("找不到这个本人学习单元，请重新打开目录。", 404)
            if result == "conflict":
                latest = next(
                    unit
                    for unit in dialogue.book_units(account.user_id, identity)
                    if unit["unit_id"] == unit_id
                )
                return book_unit_editor(
                    request,
                    item,
                    latest,
                    values,
                    message="另一页面已修改本单元："
                    + latest["title"]
                    + "，范围 "
                    + str(latest["start_pos"])
                    + "–"
                    + str(latest["end_pos"])
                    + "。你填写的内容尚未保存，已保留在下方；请核对后再次保存。",
                    code=409,
                )
        except sqlite3.Error:
            return problem("目录暂时无法保存，请返回查看，避免重复操作。", 503)
        return redirect("/web/materials/" + identity + "/plan?notice=saved")

    @app.get("/web/materials/{identity}", include_in_schema=False)
    def material_preview(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            query, scope, result_page = material_find_values(request, preview=True)
        except ValueError as error:
            return problem(str(error))
        try:
            item = materials.get(account.user_id, identity)
            chunks = materials.chunks(account.user_id, identity) if item else []
            if not item or not chunks:
                return problem("找不到这份可读取资料。", 404)
            if scope and materials.get(account.user_id, scope) is None:
                return problem("找不到这份可读取资料。", 404)
            find_values = (
                {"find": query, "find_material": scope, "find_page": result_page}
                if query
                else {}
            )
            find_hidden = "".join(
                '<input type="hidden" name="'
                + key
                + '" value="'
                + escape(str(value), quote=True)
                + '">'
                for key, value in find_values.items()
            )
            find_back = (
                '<a class="text-link" href="'
                + escape(
                    "/web/materials/find?"
                    + urlencode({"q": query, "material": scope, "page": result_page}),
                    quote=True,
                )
                + '">← 返回原文查找结果</a>'
                if query
                else ""
            )
            navigation = (
                '<div class="material-locate"><form method="get" action="/web/materials/'
                + identity
                + '"><label for="material-part">跳到文字片段</label><input id="material-part" name="part" type="number" min="1" max="'
                + str(len(chunks))
                + '" required>'
                + find_hidden
                + '<button class="button button-outline" type="submit">定位片段</button></form>'
            )
            if item["kind"] == "pdf":
                navigation += (
                    '<form method="get" action="/web/materials/'
                    + identity
                    + '"><label for="material-page">跳到 PDF 文件页码</label><input id="material-page" name="page" type="number" min="1" max="'
                    + str(item["page_count"])
                    + '" required>'
                    + find_hidden
                    + '<button class="button button-outline" type="submit">定位页码</button></form><p class="lesson-revision-note">PDF 文件页码可能不同于书内印刷页码；每页可能分成多个文字片段。</p>'
                )
            navigation += "</div>"
            number = int(request.query_params.get("part", "1"))
            if "page" in request.query_params:
                requested_page = int(request.query_params["page"])
                if (
                    item["kind"] != "pdf"
                    or not 1 <= requested_page <= item["page_count"]
                ):
                    raise ValueError("invalid PDF page")
                number = next(
                    (
                        index + 1
                        for index, part in enumerate(chunks)
                        if part["locator"].startswith(f"PDF 第 {requested_page} 页 ·")
                    ),
                    None,
                )
                if number is None:
                    return page(
                        item["title"],
                        '<p class="library-intro">这一页没有可提取的文字，尚未选入对话。请换一个页码，或按文字片段定位。</p>'
                        + navigation
                        + find_back
                        + '<a class="text-link" href="/web/materials/'
                        + identity
                        + (
                            "?" + escape(urlencode(find_values), quote=True)
                            if query
                            else ""
                        )
                        + '">回到第一个可读片段 →</a>',
                    )
            if not 1 <= number <= len(chunks):
                return problem("找不到这份资料或片段。", 404)
            chunk = chunks[number - 1]
            controls = action(
                request,
                f"/web/materials/{identity}/select",
                "select",
                identity,
                "围绕整份资料讨论",
            )
            controls += (
                '<form method="post" action="/web/materials/'
                + identity
                + '/study">'
                + input_csrf(request, "study-part", identity + "." + chunk["chunk_id"])
                + '<input type="hidden" name="chunk_id" value="'
                + chunk["chunk_id"]
                + '"><button class="button button-primary" type="submit">选中这段，回到对话</button></form>'
            )
            previous = (
                '<a href="?'
                + escape(urlencode({"part": number - 1, **find_values}), quote=True)
                + '">← 上一片段</a>'
                if number > 1
                else ""
            )
            following = (
                '<a href="?'
                + escape(urlencode({"part": number + 1, **find_values}), quote=True)
                + '">下一片段 →</a>'
                if number < len(chunks)
                else ""
            )
            matching = ""
            if query:
                matches = match_contexts(chunk["content"], query, limit=1)
                matching = (
                    '<section id="material-find" class="library-card lesson-find"><h2>关键词附近原文</h2><p>查找：'
                    + escape(query)
                    + "</p>"
                    + find_back
                )
                if matches["count"]:
                    matching += (
                        '<p class="lesson-search-label">本片段有 '
                        + str(matches["count"])
                        + " 处匹配，下方展示首处附近原文；完整片段保留在后面。</p>"
                    )
                    matching += search_excerpt(
                        {
                            "search_match": {
                                "fields": ["原文"],
                                "excerpt": matches["contexts"][0],
                            }
                        },
                        query,
                    )
                else:
                    matching += (
                        "<p>当前片段没有匹配文字，可以查看相邻片段或返回查找结果。</p>"
                    )
                matching += "</section>"
            note = (
                "<p>部分页面没有可提取文字，当前检索范围为已提取内容。</p>"
                if item["kind"] == "pdf" and item["readable_pages"] < item["page_count"]
                else ""
            )
            return page(
                item["title"],
                '<p class="library-intro">文字预览 · '
                + escape(chunk["locator"])
                + f" · 共 {len(chunks)} 个片段</p>"
                + note
                + '<p><a class="text-link" href="/web/materials/'
                + identity
                + '/plan">书籍学习目录与进度 →</a></p>'
                + material_search_form([item], scope=identity, query=query)
                + navigation
                + matching
                + '<p class="lesson-revision-note">当前仅预览。选中这段后，可在统一对话中点击“讲解并提炼这段”；浏览和选段不调用 AI。</p><div class="library-actions">'
                + controls
                + "</div>"
                + '<article class="library-document">'
                + search_highlight(chunk["content"], query)
                + '</article><nav class="library-paging">'
                + previous
                + following
                + "</nav>",
            )
        except ValueError:
            return problem("请输入这份资料范围内的有效页码或片段编号。")
        except sqlite3.Error:
            return problem("资料暂时无法读取。", 503)

    @app.post("/web/materials/{identity}/study", include_in_schema=False)
    async def select_study_part(request: Request, identity: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf", "chunk_id"}, limit=4096)
        chunk_id = values.get("chunk_id", "") if values else ""
        if not re.fullmatch(r"[a-f0-9]{32}", chunk_id) or not valid_csrf(
            request, values, "study-part", identity + "." + chunk_id
        ):
            return problem("选段页面无法核对，请重新打开资料。", 403)
        try:
            item = materials.get(account.user_id, identity)
            chunk = materials.chunk(account.user_id, identity, chunk_id)
            if item is None or chunk is None:
                return problem("找不到这份本人资料或选段。", 404)
            await run_in_threadpool(
                dialogue.select_material_part,
                account.user_id,
                identity,
                item["title"],
                chunk_id,
            )
        except TopicBusy as error:
            return problem(str(error), 409)
        except sqlite3.Error:
            return problem("暂时无法保存选段，请稍后再试。", 503)
        return redirect("/web/welcome#coach-dialog")

    @app.post("/web/materials/{identity}/select", include_in_schema=False)
    async def select(request: Request, identity: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf"}, limit=2048)
        if not valid_csrf(request, values, "select", identity):
            return problem("页面无法核对。", 403)
        try:
            await run_in_threadpool(
                select_discussion_material,
                dialogue,
                materials,
                account.user_id,
                identity,
            )
            return redirect("/web/welcome#coach-dialog")
        except TopicBusy as error:
            return problem(str(error), 409)
        except (ValueError, sqlite3.Error):
            return problem("这份资料当前无法选用。", 404)

    @app.post("/web/materials/clear", include_in_schema=False)
    async def clear(request: Request):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf"}, limit=2048)
        if not valid_csrf(request, values, "clear"):
            return problem("页面无法核对。", 403)
        try:
            await run_in_threadpool(
                select_discussion_material, dialogue, materials, account.user_id, None
            )
            return redirect("/web/welcome#coach-dialog")
        except TopicBusy as error:
            return problem(str(error), 409)
        except sqlite3.Error:
            return problem("暂时无法更新资料选择。", 503)

    @app.get("/web/knowledge", include_in_schema=False)
    def knowledge_list(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        status = request.query_params.get("status", "saved")
        try:
            query = search_query(request.query_params.get("q", ""))
            number = int(request.query_params.get("page", "1"))
            if status not in {"saved", "pending"} or not 1 <= number <= 1000000:
                return problem("查询条件无法读取。")
        except ValueError as error:
            return problem(str(error))
        try:
            items = dialogue.list_knowledge(
                account.user_id, status=status, query=query, offset=(number - 1) * 20
            )
        except sqlite3.Error:
            return problem("暂时无法读取知识库。", 503)
        cards = ""
        for item in items[:20]:
            url = "/web/knowledge/" + item["knowledge_id"]
            if query:
                url += (
                    "?"
                    + urlencode({"find": query, "result_page": number})
                    + "#lesson-find"
                )
            cards += (
                '<article class="library-item"><span class="library-badge">'
                + ("待你确认" if status == "pending" else "已保存教案")
                + '</span><h2><a href="'
                + escape(url, quote=True)
                + '">'
                + escape(item["title"])
                + "</a></h2><p>"
                + escape(item["topic"])
                + "</p>"
                + search_excerpt(item, query)
                + '<a class="text-link" href="'
                + escape(url, quote=True)
                + '">'
                + ("预览与保存教案 →" if status == "pending" else "调阅、修订与重温 →")
                + "</a></article>"
            )
        paging = ""
        for target, label in ((number - 1, "← 上一页"), (number + 1, "下一页 →")):
            if (target < number and number > 1) or (
                target > number and len(items) > 20
            ):
                paging += (
                    '<a href="?'
                    + escape(
                        urlencode({"status": status, "q": query, "page": target}),
                        quote=True,
                    )
                    + '">'
                    + label
                    + "</a>"
                )
        search = (
            '<form class="library-search" method="get"><input type="hidden" name="status" value="'
            + status
            + '"><label class="visually-hidden" for="knowledge-query">查找标题、主题或正文</label><input id="knowledge-query" name="q" maxlength="120" placeholder="查找标题、主题或正文" value="'
            + escape(query, quote=True)
            + '"><button class="button button-outline">查找</button></form>'
        )
        if query:
            search += (
                '<p class="lesson-search-label">按输入文字查找当前版本；不调用 AI。<a class="text-link" href="?status='
                + status
                + '">清除查找</a></p>'
            )
        empty = (
            "没有找到匹配内容。可以缩短关键词、换一句原文，或切换已保存与草稿目录查找。"
            if query
            else "这里还没有内容。可以在对话中说“把这个知识点整理成教案”。草稿先在这里预览、修改并确认保存，之后进入已保存目录。"
        )
        tabs = '<nav class="library-tabs">'
        for state, label in (
            ("saved", "已保存的教案目录"),
            ("pending", "教案草稿 · 预览与保存"),
        ):
            target = "/web/knowledge?" + urlencode({"status": state, "q": query})
            tabs += (
                '<a href="'
                + escape(target, quote=True)
                + '"'
                + (' aria-current="page"' if status == state else "")
                + ">"
                + label
                + "</a>"
            )
        tabs += '<a href="/web/booklets">我的学习手册 · 教案成册</a></nav>'
        return page(
            "知识资产沉淀",
            '<p class="library-intro">经你确认的教案、知识点和学习册，留在这里，随时可以重温。</p>'
            + tabs
            + search
            + '<div class="library-list">'
            + (cards or '<p class="library-empty">' + empty + "</p>")
            + '</div><nav class="library-paging">'
            + paging
            + "</nav>",
        )

    @app.get("/web/knowledge/{identity}", include_in_schema=False)
    def knowledge_preview(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            query = search_query(request.query_params.get("find", ""))
            number = request.query_params.get("result_page", "1")
            if not re.fullmatch(r"[1-9][0-9]{0,5}|1000000", number):
                return problem("返回结果的页码无法读取。")
            booklet = request.query_params.get("booklet", "")
            if booklet and not re.fullmatch(r"[a-f0-9]{32}", booklet):
                return problem("来源手册无法读取。")
        except ValueError as error:
            return problem(str(error))
        try:
            item = dialogue.knowledge(account.user_id, identity)
            if (
                booklet
                and dialogue.booklet(account.user_id, booklet, chapter=0) is None
            ):
                return problem("找不到这本本人手册。", 404)
        except sqlite3.Error:
            return problem("暂时无法读取教案。", 503)
        if not item:
            return problem("找不到这份教案。", 404)
        matching = ""
        if query:
            back = (
                (
                    "/web/booklets/"
                    + booklet
                    + "/edit?"
                    + urlencode({"q": query, "page": number})
                    + "#booklet-add"
                )
                if booklet
                else (
                    "/web/knowledge?"
                    + urlencode({"q": query, "status": item["status"], "page": number})
                )
            )
            matches = match_contexts(item["content"], query)
            matching = (
                '<section id="lesson-find" class="library-card lesson-find"><h2>查找匹配位置</h2><p>查找：'
                + escape(query)
                + '</p><a class="text-link" href="'
                + escape(back, quote=True)
                + '">'
                + ("返回手册收录结果" if booklet else "返回查找结果")
                + " →</a>"
            )
            if matches["count"]:
                matching += (
                    '<p class="lesson-search-label">当前正文共 '
                    + str(matches["count"])
                    + " 处匹配，展示 "
                    + str(len(matches["contexts"]))
                    + " 段附近原文，最多五段；完整教案在下方。</p>"
                )
                for excerpt in matches["contexts"]:
                    matching += (
                        '<p class="lesson-search-excerpt">'
                        + ("…" if excerpt["before"] else "")
                        + search_highlight(excerpt["text"], query)
                        + ("…" if excerpt["after"] else "")
                        + "</p>"
                    )
            else:
                matching += "<p>当前正文没有匹配文字。关键词可能匹配标题或主题，或教案已经修订；可查看下方全文，或返回结果重新查找。</p>"
            matching += "</section>"
        if item["status"] == "pending":
            controls = (
                '<p class="library-intro">这是待确认草稿，尚未进入已保存知识库。可以修改后确认，也可以暂不保存。</p><article class="lesson-document markdown-content">'
                + lesson_html(item["content"])
                + '</article><form method="post" action="/web/knowledge/'
                + identity
                + '/save">'
                + input_csrf(request, "save", identity)
                + '<details class="lesson-edit"><summary>修改草稿标题和正文</summary><label for="lesson-title">教案标题</label><input id="lesson-title" name="title" maxlength="120" required value="'
                + escape(item["title"], quote=True)
                + '"><label for="lesson-content">教案正文（可以修改）</label><textarea id="lesson-content" name="content" rows="22" maxlength="12000" required>'
                + escape(item["content"])
                + '</textarea></details><button class="button button-primary" type="submit">确认保存到知识库</button></form>'
                + action(
                    request,
                    f"/web/knowledge/{identity}/dismiss",
                    "dismiss",
                    identity,
                    "暂不保存这份草稿",
                )
            )
        else:
            controls = (
                '<p class="library-intro">已由你确认保存。当前为第 '
                + str(item["revision"])
                + " 版 · "
                + lesson_time(item["revised_at"])
                + "</p>"
                + lesson_notice(request.query_params.get("notice"))
                + '<div class="library-actions">'
                + action(
                    request,
                    f"/web/knowledge/{identity}/review",
                    "review",
                    identity,
                    "在对话中重温",
                )
                + f'<a class="button button-outline" href="/web/knowledge/{identity}/download">导出教案</a><a class="button button-outline" href="/web/knowledge/{identity}/edit">修改教案</a><a class="text-link" href="/web/knowledge/{identity}/versions">版本记录</a></div><article class="lesson-document markdown-content">'
                + lesson_html(item["content"])
                + "</article>"
            )
        citations = "".join(
            '<details class="citation"><summary>整理时参考：'
            + escape(source["title"] + " · " + source["locator"])
            + "</summary><p>"
            + escape(source["excerpt"])
            + "</p></details>"
            for source in item["citations"]
        )
        return page(
            item["title"],
            matching
            + '<section class="library-card">'
            + (
                '<div class="book-study-summary"><p>'
                + escape(unit_scope_text(item["unit_summary"])).replace("\n", "<br>")
                + '</p><a class="text-link" href="/web/materials/'
                + item["unit_summary"]["material_id"]
                + "/plan/"
                + item["unit_summary"]["unit_id"]
                + '/lessons">回到本单元教案与整理 →</a></div>'
                if item.get("unit_summary")
                else ""
            )
            + controls
            + citations
            + (
                '<p class="lesson-revision-note">修订由你维护；引用记录最初整理时的参考，不代表新增内容已由原书核实。重温和导出使用当前版本。</p>'
                if item["status"] == "saved"
                else ""
            )
            + "</section>",
        )

    def lesson_time(timestamp):
        return datetime.fromtimestamp(timestamp, timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M · 北京时间"
        )

    def lesson_notice(notice):
        message = {
            "revised": "修订已保存，旧版本已保留。",
            "restored": "所选内容已恢复为新的当前版本，原有版本均保留。",
            "unchanged": "内容与当前版本相同，没有重复创建版本。",
        }.get(notice)
        return (
            '<p class="lesson-version-notice" role="status">' + message + "</p>"
            if message
            else ""
        )

    def revision_number(text):
        return (
            int(text)
            if re.fullmatch(r"[1-9][0-9]{0,9}", text) and int(text) <= 1000000000
            else None
        )

    def lesson_editor(request, item, values=None, *, message="", code=200):
        values = values or item
        identity, revision = item["knowledge_id"], str(item["revision"])
        body = (
            '<p class="library-intro">修改第 '
            + revision
            + " 版教案，保存后会保留旧版。普通编辑不调用 AI。</p>"
        )
        if message:
            body += (
                '<p class="form-error-summary" role="alert">'
                + escape(message)
                + '</p><details class="lesson-current-comparison"><summary>查看当前已保存内容，再决定如何合并</summary><h2>'
                + escape(item["title"])
                + '</h2><article class="lesson-document markdown-content">'
                + lesson_html(item["content"])
                + "</article></details>"
            )
        body += (
            '<section class="library-card lesson-revision-editor"><form method="post" action="/web/knowledge/'
            + identity
            + '/revise">'
            + input_csrf(request, "revise", identity + "." + revision)
        )
        body += (
            '<input type="hidden" name="revision" value="'
            + revision
            + '"><label for="revision-title">教案标题</label><input id="revision-title" name="title" maxlength="120" required value="'
            + escape(values["title"], quote=True)
            + '"><label for="revision-content">教案正文（支持 Markdown）</label><textarea id="revision-content" name="content" rows="24" maxlength="12000" required>'
            + escape(values["content"])
            + '</textarea><p class="lesson-revision-note">保存前请核对内容；引用继续保留为最初整理时的参考。未保存的修改不会自动保留，离开前请先保存或自行复制。</p><div class="library-actions"><button class="button button-primary" type="submit">'
            + ("再次确认并保存修订" if code == 409 else "保存修订")
            + '</button><a class="button button-outline" href="/web/knowledge/'
            + identity
            + '">取消，回到教案</a></div></form></section>'
        )
        return page("修改教案", body, code=code)

    def version_reading(request, item, version, *, message="", code=200):
        identity = item["knowledge_id"]
        current, target = str(item["revision"]), str(version["revision"])
        body = (
            '<p class="library-intro">第 '
            + target
            + " 版 · "
            + lesson_time(version["created_at"])
            + (" · 当前版本" if current == target else " · 历史版本")
            + "</p>"
        )
        if message:
            body += (
                '<p class="form-error-summary" role="alert">' + escape(message) + "</p>"
            )
        body += (
            '<div class="library-actions"><a class="button button-outline" href="/web/knowledge/'
            + identity
            + '">回到当前教案</a><a class="text-link" href="/web/knowledge/'
            + identity
            + '/versions">全部版本记录</a></div><article class="library-card lesson-document markdown-content">'
            + lesson_html(version["content"])
            + "</article>"
        )
        if current != target:
            body += (
                '<section class="library-card"><h2>恢复为当前内容</h2><p class="lesson-revision-note">当前是第 '
                + current
                + " 版。确认后将以第 "
                + target
                + ' 版的标题和正文建立新版，之后的版本仍然保留；恢复本身不调用 AI。若内容相同，不重复建立版本。</p><form method="post" action="/web/knowledge/'
                + identity
                + '/restore">'
                + input_csrf(
                    request, "restore", identity + "." + current + "." + target
                )
                + '<input type="hidden" name="revision" value="'
                + current
                + '"><input type="hidden" name="target" value="'
                + target
                + '"><button class="button button-primary" type="submit">确认恢复第 '
                + target
                + " 版内容</button></form></section>"
            )
        return page(version["title"], body, code=code)

    @app.get("/web/knowledge/{identity}/edit", include_in_schema=False)
    def edit_lesson(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            item = dialogue.knowledge(account.user_id, identity, saved_only=True)
        except sqlite3.Error:
            return problem("暂时无法读取教案。", 503)
        return (
            lesson_editor(request, item)
            if item
            else problem("找不到已保存的教案。", 404)
        )

    @app.get("/web/knowledge/{identity}/versions", include_in_schema=False)
    def lesson_versions(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        number = revision_number(request.query_params.get("page", "1"))
        if number is None or number > 100000:
            return problem("请检查版本页码。")
        try:
            item = dialogue.knowledge(account.user_id, identity, saved_only=True)
            if not item:
                return problem("找不到已保存的教案。", 404)
            versions = dialogue.knowledge_versions(
                account.user_id, identity, offset=(number - 1) * 20
            )
        except sqlite3.Error:
            return problem("暂时无法读取版本记录。", 503)
        body = (
            '<p class="library-intro">'
            + escape(item["title"])
            + " · 当前为第 "
            + str(item["revision"])
            + ' 版。每次修订都留一份记录，恢复旧版会建立新版。</p><a class="text-link" href="/web/knowledge/'
            + identity
            + '">← 回到当前教案</a><div class="lesson-version-list">'
        )
        for version in versions[:20]:
            revision = str(version["revision"])
            label = (
                "首次保存"
                if version["revision"] == 1
                else (
                    "恢复自第 " + str(version["restored_from"]) + " 版"
                    if version["restored_from"]
                    else "手动修订"
                )
            )
            body += (
                '<article class="library-item"><span class="library-badge">第 '
                + revision
                + " 版"
                + (" · 当前版本" if version["revision"] == item["revision"] else "")
                + '</span><h2><a href="/web/knowledge/'
                + identity
                + "/versions/"
                + revision
                + '">'
                + escape(version["title"])
                + "</a></h2><p>"
                + label
                + " · "
                + lesson_time(version["created_at"])
                + '</p><a class="text-link" href="/web/knowledge/'
                + identity
                + "/versions/"
                + revision
                + '">查看本版内容 →</a></article>'
            )
        body += '</div><nav class="library-paging" aria-label="教案版本分页">'
        if number > 1:
            body += '<a href="?page=' + str(number - 1) + '">← 上一页</a>'
        if len(versions) > 20:
            body += '<a href="?page=' + str(number + 1) + '">下一页 →</a>'
        return page("版本记录", body + "</nav>")

    @app.get("/web/knowledge/{identity}/versions/{version}", include_in_schema=False)
    def read_lesson_version(request: Request, identity: str, version: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        number = revision_number(version)
        if number is None:
            return problem("找不到这个教案版本。", 404)
        try:
            item = dialogue.knowledge(account.user_id, identity, saved_only=True)
            record = dialogue.knowledge_version(account.user_id, identity, number)
        except sqlite3.Error:
            return problem("暂时无法读取教案版本。", 503)
        return (
            version_reading(request, item, record)
            if item and record
            else problem("找不到这个教案版本。", 404)
        )

    async def revision_action(request, user_id, identity, operation):
        expected = (
            {"csrf", "revision", "title", "content"}
            if operation == "revise"
            else {"csrf", "revision", "target"}
        )
        values = await fields(request, expected)
        if values is None:
            return problem("修订内容格式无法读取或过长，请返回教案重新填写。")
        revision = revision_number(values["revision"])
        target = revision_number(values["target"]) if operation == "restore" else None
        binding = (
            identity
            + "."
            + values["revision"]
            + ("." + values["target"] if operation == "restore" else "")
        )
        if (
            revision is None
            or (operation == "restore" and target is None)
            or not valid_csrf(request, values, operation, binding)
            or (
                request.headers.get("origin") == "null"
                and request.headers.get("sec-fetch-site") != "same-origin"
            )
        ):
            return problem("页面无法核对，请重新打开教案。", 403)
        try:
            item = dialogue.knowledge(user_id, identity, saved_only=True)
            if not item:
                return problem("找不到已保存的教案。", 404)
            record = (
                dialogue.knowledge_version(user_id, identity, target)
                if target
                else None
            )
            if target and not record:
                return problem("找不到这个教案版本。", 404)
            try:
                result = await run_in_threadpool(
                    dialogue.revise_knowledge,
                    user_id,
                    identity,
                    revision,
                    **(
                        {"restore": target}
                        if target
                        else {"title": values["title"], "content": values["content"]}
                    ),
                )
            except TopicBusy:
                message = "教练正在重温这份教案，请等本轮回复结束后再保存。你的填写内容仍在下方。"
                return (
                    lesson_editor(request, item, values, message=message, code=409)
                    if operation == "revise"
                    else version_reading(
                        request,
                        item,
                        record,
                        message="教练正在重温这份教案，请等回复结束后再恢复。",
                        code=409,
                    )
                )
            except ValueError:
                return (
                    lesson_editor(
                        request,
                        item,
                        values,
                        message="标题需要 1–120 字，正文需要 1–12000 字；标题不含换行，内容不含无效字符。",
                    )
                    if operation == "revise"
                    else problem("恢复信息无法读取。")
                )
            if result == "missing":
                return problem("找不到这个教案或版本。", 404)
            if result == "conflict":
                latest = dialogue.knowledge(user_id, identity, saved_only=True)
                return (
                    lesson_editor(
                        request,
                        latest,
                        values,
                        message="另一页面已经保存了新版。本次填写尚未保存，已保留在下方，请先展开当前内容核对，合并后再确认。",
                        code=409,
                    )
                    if operation == "revise"
                    else version_reading(
                        request,
                        latest,
                        record,
                        message="另一页面已经保存了新版。请核对当前版本后，再决定是否恢复。",
                        code=409,
                    )
                )
        except sqlite3.Error:
            return problem("教案暂时无法保存，请先查看当前版本，避免重复操作。", 503)
        notice = (
            "unchanged"
            if result == "unchanged"
            else "restored"
            if operation == "restore"
            else "revised"
        )
        return redirect("/web/knowledge/" + identity + "?notice=" + notice)

    @app.post("/web/knowledge/{identity}/{operation}", include_in_schema=False)
    async def knowledge_action(request: Request, identity: str, operation: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        if operation not in {"save", "dismiss", "review", "revise", "restore"}:
            return problem("找不到这项操作。", 404)
        if operation in {"revise", "restore"}:
            return await revision_action(request, account.user_id, identity, operation)
        values = await fields(
            request, {"csrf", "title", "content"} if operation == "save" else {"csrf"}
        )
        if not valid_csrf(request, values, operation, identity):
            return problem("页面无法核对，请重新打开教案。", 403)
        try:
            item = await run_in_threadpool(
                dialogue.knowledge, account.user_id, identity
            )
            if not item:
                return problem("找不到这份教案。", 404)
            if operation == "review":
                source = (
                    item["citations"][0]["material_id"] if item["citations"] else None
                )
                if source and materials.get(account.user_id, source) is None:
                    source = None
                await run_in_threadpool(
                    dialogue.select_review,
                    account.user_id,
                    identity,
                    material_id=source or "",
                )
                return redirect("/web/welcome#coach-dialog")
            await run_in_threadpool(
                dialogue.confirm_knowledge,
                account.user_id,
                identity,
                save=operation == "save",
                title=values.get("title"),
                content=values.get("content"),
            )
            return redirect(
                "/web/knowledge/" + identity
                if operation == "save"
                else "/web/knowledge?status=pending"
            )
        except TopicBusy as error:
            return problem(str(error), 409)
        except ValueError:
            return problem("请检查标题和正文长度，或确认教案已经保存。")
        except sqlite3.Error:
            return problem("教案暂时无法保存，请稍后重试。", 503)

    @app.get("/web/knowledge/{identity}/download", include_in_schema=False)
    def download(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            item = dialogue.knowledge(account.user_id, identity, saved_only=True)
        except sqlite3.Error:
            return problem("教案暂时无法导出。", 503)
        if not item:
            return problem("找不到已保存的教案。", 404)
        headers = {
            **HEADERS,
            "Content-Disposition": "attachment; filename=lesson.md; filename*=UTF-8''"
            + quote(item["title"] + ".md", safe=""),
        }
        content = item["content"]
        if item.get("unit_summary"):
            content = unit_scope_text(item["unit_summary"]) + "\n\n" + content
        return Response(content, media_type="text/markdown", headers=headers)
