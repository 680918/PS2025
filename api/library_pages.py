"""Account-owned materials and explicit lesson approval. No AI calls in these routes."""

import hashlib
import hmac
import re
import secrets
import sqlite3
from html import escape
from threading import BoundedSemaphore, Lock
from urllib.parse import parse_qs, quote

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


def register_library_pages(app, accounts, materials, dialogue, *, csrf_key):
    view_limit = RegistrationRateLimiter(per_client_limit=60, total_limit=600)
    write_limit = RegistrationRateLimiter(per_client_limit=12, total_limit=60)
    upload_slots = BoundedSemaphore(2)
    export_slots = BoundedSemaphore(2)
    export_limit = RegistrationRateLimiter(per_client_limit=2, total_limit=10)

    def page(title, content, *, code=200, interactive=False):
        body = (
            '<main id="main-content" class="library-space"><nav class="library-tabs" aria-label="工作区入口"><a href="/web/welcome">← 回到对话</a><a href="/web/materials">资料与书籍</a><a href="/web/knowledge">知识资产沉淀</a><a href="/web/export">导出学习资料</a></nav><h1>'
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
            "drafts": "尚未确认的教案草稿；导出后仍保留草稿状态。",
            "chat": "你的提问、教练回复、实际引用说明，以及当前学习位置。",
            "materials": f"你上传或粘贴的原始内容，合计约 {material_size}。",
        }
        for scope, label in SCOPES.items():
            count = summary[scope]
            disabled = (
                " disabled"
                if not count and not (scope == "chat" and summary["learning"])
                else ""
            )
            checked = " checked" if scope == "saved" and count else ""
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
            + '</fieldset><div class="export-period"><label for="export-period">聊天记录时间范围</label><select id="export-period" name="period"><option value="all">全部时间</option><option value="30">最近 30 天</option><option value="90">最近 90 天</option></select><p class="export-note">只影响聊天记录；教案、资料和当前学习位置不受此选项影响。</p></div>'
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
                max_num_fields=6,
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

    @app.get("/web/materials", response_class=HTMLResponse, include_in_schema=False)
    def list_materials(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            selected, items = (
                materials.selected(account.user_id),
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
                + f' · {item["char_count"]} 字</p><div class="library-actions"><a class="text-link" href="/web/materials/{identity}">预览文字</a>'
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

    @app.get("/web/materials/{identity}", include_in_schema=False)
    def material_preview(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            item = materials.get(account.user_id, identity)
            chunks = materials.chunks(account.user_id, identity) if item else []
            number = int(request.query_params.get("part", "1"))
            if not 1 <= number <= len(chunks):
                return problem("找不到这份资料或片段。", 404)
            chunk = chunks[number - 1]
            controls = action(
                request,
                f"/web/materials/{identity}/select",
                "select",
                identity,
                "围绕这份资料讨论",
            )
            previous = (
                f'<a href="?part={number - 1}">← 上一片段</a>' if number > 1 else ""
            )
            following = (
                f'<a href="?part={number + 1}">下一片段 →</a>'
                if number < len(chunks)
                else ""
            )
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
                + controls
                + '<article class="library-document">'
                + escape(chunk["content"])
                + '</article><nav class="library-paging">'
                + previous
                + following
                + "</nav>",
            )
        except (ValueError, sqlite3.Error):
            return problem("资料暂时无法读取。", 503)

    @app.post("/web/materials/{identity}/select", include_in_schema=False)
    async def select(request: Request, identity: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        values = await fields(request, {"csrf"}, limit=2048)
        if not valid_csrf(request, values, "select", identity):
            return problem("页面无法核对。", 403)
        try:
            await run_in_threadpool(materials.select, account.user_id, identity)
            await run_in_threadpool(dialogue.select_review, account.user_id, None)
            return redirect("/web/welcome#coach-dialog")
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
            await run_in_threadpool(materials.select, account.user_id, None)
            return redirect("/web/welcome#coach-dialog")
        except sqlite3.Error:
            return problem("暂时无法更新资料选择。", 503)

    @app.get("/web/knowledge", include_in_schema=False)
    def knowledge_list(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        status = request.query_params.get("status", "saved")
        query = request.query_params.get("q", "").strip()
        try:
            number = int(request.query_params.get("page", "1"))
            if (
                status not in {"saved", "pending"}
                or not 1 <= number <= 1000000
                or len(query) > 120
            ):
                return problem("查询条件无法读取。")
            items = dialogue.list_knowledge(
                account.user_id, status=status, query=query, offset=(number - 1) * 20
            )
        except (ValueError, sqlite3.Error):
            return problem("暂时无法读取知识库。", 503)
        cards = "".join(
            '<article class="library-item"><span class="library-badge">'
            + ("待你确认" if status == "pending" else "已保存教案")
            + '</span><h2><a href="/web/knowledge/'
            + item["knowledge_id"]
            + '">'
            + escape(item["title"])
            + "</a></h2><p>"
            + escape(item["topic"])
            + '</p><a class="text-link" href="/web/knowledge/'
            + item["knowledge_id"]
            + (
                '">预览与保存教案 →</a></article>'
                if status == "pending"
                else '">调阅、重温与导出 →</a></article>'
            )
            for item in items[:20]
        )
        paging = (
            f'<a href="?status={status}&q={quote(query)}&page={number + 1}">下一页 →</a>'
            if len(items) > 20
            else ""
        )
        if number > 1:
            paging = (
                f'<a href="?status={status}&q={quote(query)}&page={number - 1}">← 上一页</a>'
                + paging
            )
        search = (
            '<form class="library-search" method="get"><input type="hidden" name="status" value="'
            + status
            + '"><label class="visually-hidden" for="knowledge-query">查找标题或主题</label><input id="knowledge-query" name="q" maxlength="120" placeholder="查找标题或主题" value="'
            + escape(query, quote=True)
            + '"><button class="button button-outline">查找</button></form>'
        )
        return page(
            "知识资产沉淀",
            '<p class="library-intro">经你确认的教案、知识点和学习册，留在这里，随时可以重温。</p><nav class="library-tabs"><a href="/web/knowledge">已保存的教案目录</a><a href="/web/knowledge?status=pending">教案草稿 · 预览与保存</a></nav>'
            + search
            + '<div class="library-list">'
            + (
                cards
                or '<p class="library-empty">这里还没有内容。可以在对话中说“把这个知识点整理成教案”。草稿先在这里预览、修改并确认保存，之后进入已保存目录。</p>'
            )
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
            item = dialogue.knowledge(account.user_id, identity)
        except sqlite3.Error:
            return problem("暂时无法读取教案。", 503)
        if not item:
            return problem("找不到这份教案。", 404)
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
                '<p class="library-intro">已由你确认保存。</p><div class="library-actions">'
                + action(
                    request,
                    f"/web/knowledge/{identity}/review",
                    "review",
                    identity,
                    "在对话中重温",
                )
                + f'<a class="button button-outline" href="/web/knowledge/{identity}/download">导出教案</a></div><article class="lesson-document markdown-content">'
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
            '<section class="library-card">' + controls + citations + "</section>",
        )

    @app.post("/web/knowledge/{identity}/{operation}", include_in_schema=False)
    async def knowledge_action(request: Request, identity: str, operation: str):
        account, denied = await run_in_threadpool(auth, request, write=True)
        if denied is not None:
            return denied
        if operation not in {"save", "dismiss", "review"}:
            return problem("找不到这项操作。", 404)
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
                await run_in_threadpool(
                    dialogue.select_review, account.user_id, identity
                )
                source = (
                    item["citations"][0]["material_id"] if item["citations"] else None
                )
                await run_in_threadpool(materials.select, account.user_id, source)
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
        return Response(item["content"], media_type="text/markdown", headers=headers)
