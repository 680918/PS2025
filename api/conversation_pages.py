"""Private read-only conversation lookup; explicit topic switching uses the study route."""

import re
import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape
from threading import BoundedSemaphore
from urllib.parse import quote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from api.coach_markdown import coach_markdown
from api.conversation_export import conversation_document
from api.library_pages import HEADERS, library_csrf, search_highlight
from api.public_pages import _render_layout
from coach.knowledge_search import search_query, match_contexts
from coach.conversation_dates import conversation_date_window
from security.login_sessions import signed_in_account
from security.registration_rate_limit import RegistrationRateLimiter


def register_conversation_pages(app, accounts, dialogue, *, csrf_key):
    views = RegistrationRateLimiter(per_client_limit=40, total_limit=400)
    downloads = RegistrationRateLimiter(per_client_limit=6, total_limit=60)
    download_slots = BoundedSemaphore(2)

    def page(title, body, code=200, *, copy=False):
        content = (
            '<main id="main-content" class="library-space conversation-review-space">'
            '<nav class="library-tabs" aria-label="工作区入口"><a href="/web/welcome">← 回到对话</a>'
            '<a href="/web/conversations" aria-current="page">对话记录</a>'
            '<a href="/web/studies">我的学习</a><a href="/web/materials">资料与书籍</a>'
            '<a href="/web/knowledge">知识资产沉淀</a><a href="/web/export">导出学习资料</a></nav>'
            "<h1>" + escape(title) + "</h1>" + body + "</main>"
        )
        if copy:
            content += '<script src="/static/content-copy.js?v=1" defer></script>'
        return HTMLResponse(
            _render_layout(title + " · 知行", content, signed_in=True),
            status_code=code,
            headers={
                **HEADERS,
                "Content-Security-Policy": "default-src 'none'; style-src 'self'; script-src 'self'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            }
            if copy
            else HEADERS,
        )

    def problem(text, code=400):
        return page(
            "对话记录暂未打开",
            '<p class="form-error-summary" role="alert">'
            + escape(text)
            + '</p><a class="button button-outline" href="/web/conversations">返回对话记录</a>',
            code,
        )

    def auth(request):
        wait = views.admit(request.client.host if request.client else "unknown")
        if wait:
            response = problem("查看较频繁，请稍后再试。", 429)
            response.headers["Retry-After"] = str(wait)
            return None, response
        try:
            account = signed_in_account(
                accounts, request.cookies.get("coach_login_session")
            )
        except sqlite3.Error:
            return None, problem("暂时无法核对登录状态。", 503)
        return (
            (account, None)
            if account
            else (
                None,
                RedirectResponse("/web/login", status_code=303, headers=HEADERS),
            )
        )

    def filters(request):
        if any(
            len(request.query_params.getlist(name)) > 1
            for name in ("q", "topic", "page", "start", "end")
        ):
            raise ValueError("查找条件重复，请重新输入。")
        query = search_query(request.query_params.get("q", ""))
        topic = request.query_params.get("topic", "")
        number = request.query_params.get("page", "1")
        if (
            topic not in {"", "unfiled"}
            and re.fullmatch(r"[a-f0-9]{32}", topic) is None
        ):
            raise ValueError("请选择有效的对话主题。")
        if re.fullmatch(r"[1-9][0-9]{0,4}", number) is None or int(number) > 10000:
            raise ValueError("请输入有效的对话记录页码。")
        start, end = (
            request.query_params.get("start", ""),
            request.query_params.get("end", ""),
        )
        conversation_date_window(start, end)
        values = {"q": query, "topic": topic, "page": int(number)}
        if start:
            values["start"] = start
        if end:
            values["end"] = end
        return values

    def url(values, *, turn=None, **changes):
        path = "/web/conversations" + ("/" + str(turn) if turn is not None else "")
        return path + "?" + urlencode({**values, **changes})

    def stamp(item):
        return (
            datetime.fromtimestamp(
                item["created_at"], timezone(timedelta(hours=8))
            ).strftime("%Y-%m-%d %H:%M")
            + " · 北京时间"
        )

    def status(item):
        return {"complete": "已回复", "pending": "尚未完成", "failed": "未取得回复"}[
            item["status"]
        ]

    def excerpt(item, query):
        return (
            '<div class="conversation-record-excerpt"><p class="lesson-search-label">'
            + escape(item["speaker"])
            + '</p><p class="lesson-search-excerpt">'
            + ("…" if item["before"] else "")
            + search_highlight(item["text"], query)
            + ("…" if item["after"] else "")
            + "</p></div>"
        )

    @app.get("/web/conversations", include_in_schema=False)
    def index(request: Request):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            values = filters(request)
            selected = (
                dialogue.topic(account.user_id, values["topic"])
                if values["topic"] not in {"", "unfiled"}
                else None
            )
            if values["topic"] not in {"", "unfiled"} and selected is None:
                return problem("找不到这个学习主题。", 404)
            records = dialogue.conversation_records(
                account.user_id,
                query=values["q"],
                topic_id=values["topic"],
                page=values["page"],
                start_day=values.get("start", ""),
                end_day=values.get("end", ""),
            )
            topics = dialogue.list_topics(account.user_id, limit=101)
        except ValueError as error:
            return problem(str(error))
        except sqlite3.Error:
            return problem("暂时无法读取对话记录，请稍后再试。", 503)
        recent = topics[:100]
        if selected and all(
            item["topic_id"] != selected["topic_id"] for item in recent
        ):
            recent.append(selected)
        choices = [("", "全部对话"), ("unfiled", "未归入学习主题的记录")]
        choices += [(item["topic_id"], item["title"]) for item in recent]
        options = "".join(
            '<option value="'
            + identity
            + '"'
            + (" selected" if values["topic"] == identity else "")
            + ">"
            + escape(title)
            + "</option>"
            for identity, title in choices
        )
        body = (
            '<p class="library-intro">找回以前的讨论，让理解可以再次接续。</p>'
            '<form class="material-search-form library-card" method="get" action="/web/conversations">'
            '<div><label for="conversation-query">查找以前的对话</label><input id="conversation-query" type="search" name="q" maxlength="120" value="'
            + escape(values["q"], quote=True)
            + '" placeholder="输入关键词；留空查看全部"></div>'
            '<div><label for="conversation-topic">对话主题</label><select id="conversation-topic" name="topic">'
            + options
            + "</select></div>"
            + '<div class="conversation-date-field"><label for="conversation-start">开始日期（可选）</label><input id="conversation-start" type="date" name="start" value="'
            + escape(values.get("start", ""), quote=True)
            + '"></div>'
            + '<div class="conversation-date-field"><label for="conversation-end">结束日期（可选）</label><input id="conversation-end" type="date" name="end" value="'
            + escape(values.get("end", ""), quote=True)
            + '"></div>'
            + '<button class="button button-primary" type="submit">查看记录</button></form>'
            '<p class="lesson-search-label">按原文字词查找你的消息和已保存回复，每页最多 20 轮。回看不调用 AI，也不切换当前学习位置。早期未分类记录保留原状。</p>'
            '<p class="lesson-search-label">日期按发起对话的北京时间计算，开始和结束当天都包含；留空则不限制这一端日期。</p>'
        )
        if values.get("start") or values.get("end"):
            body += (
                '<p><a class="text-link" href="'
                + escape(url(values, start="", end="", page=1), quote=True)
                + '">清除日期限制</a></p>'
            )
        if len(topics) > 100:
            body += '<p class="lesson-search-label">下拉显示最近更新的 100 个主题；其他主题可从“我的学习”的“回看主题对话”进入。</p>'
        body += (
            '<h2 class="material-results-title">'
            + ("“" + escape(values["q"]) + "” · " if values["q"] else "对话记录 · ")
            + "第 "
            + str(values["page"])
            + ' 页</h2><div class="conversation-record-list">'
        )
        for item in records[:20]:
            body += (
                '<article class="library-card conversation-record-card"><p class="conversation-record-meta">'
                + escape(stamp(item))
                + " · "
                + status(item)
                + "</p>"
                "<h2>"
                + escape(item["topic_title"] or "未归入学习主题")
                + "</h2>"
                + "".join(excerpt(part, values["q"]) for part in item["excerpts"])
                + '<a class="text-link conversation-record-link" href="'
                + escape(url(values, turn=item["turn_id"]), quote=True)
                + '">查看完整问答与引用 →</a></article>'
            )
        if not records:
            body += (
                '<p class="library-empty">'
                + (
                    "没有找到匹配对话。可以缩短关键词或更换主题。"
                    if values["q"]
                    else "这一页没有对话记录，可以返回上一页或重新查找。"
                    if values["page"] > 1
                    else "这里还没有对话记录。回到统一聊天框，开始一次交流。"
                )
                + "</p>"
            )
        body += '</div><nav class="library-paging" aria-label="对话记录翻页">'
        for target, label, visible in (
            (values["page"] - 1, "← 上一页", values["page"] > 1),
            (
                values["page"] + 1,
                "下一页 →",
                len(records) > 20 and values["page"] < 10000,
            ),
        ):
            if visible:
                body += (
                    '<a href="'
                    + escape(url(values, page=target), quote=True)
                    + '">'
                    + label
                    + "</a>"
                )
        body += "</nav>"
        return page("对话记录", body)

    @app.get("/web/conversations/{identity}/download", include_in_schema=False)
    def download(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        if request.headers.get("sec-fetch-site") == "cross-site" or request.headers.get(
            "origin"
        ) not in {None, f"{request.url.scheme}://{request.url.netloc}"}:
            return problem("请从本人对话记录页面下载。", 403)
        if (
            re.fullmatch(r"[1-9][0-9]{0,18}", identity) is None
            or int(identity) > 9223372036854775807
        ):
            return problem("找不到这轮对话。", 404)
        if request.query_params:
            return problem("下载不接受额外参数，请从完整问答页面重新打开。")
        wait = downloads.admit(account.user_id)
        if wait:
            response = problem("问答下载较频繁，请稍后再试。", 429)
            response.headers["Retry-After"] = str(wait)
            return response
        if not download_slots.acquire(blocking=False):
            return problem("已有问答正在准备，请稍后再试。", 503)
        try:
            item = dialogue.conversation_record(account.user_id, int(identity))
            if item is None:
                return problem("找不到这轮对话。", 404)
            content, name = conversation_document(item)
            return Response(
                content,
                media_type="application/octet-stream",
                headers={
                    **HEADERS,
                    "Content-Disposition": f"attachment; filename=\"zhixing-dialogue-{identity}.html\"; filename*=UTF-8''"
                    + quote(name, safe=""),
                },
            )
        except (sqlite3.Error, ValueError, TypeError, KeyError, OverflowError):
            return problem(
                "这轮问答暂时无法下载，可稍后重试或使用完整学习资料导出。", 503
            )
        finally:
            download_slots.release()

    @app.get("/web/conversations/{identity}", include_in_schema=False)
    def detail(request: Request, identity: str):
        account, denied = auth(request)
        if denied is not None:
            return denied
        try:
            values = filters(request)
        except ValueError as error:
            return problem(str(error))
        if (
            re.fullmatch(r"[1-9][0-9]{0,18}", identity) is None
            or int(identity) > 9223372036854775807
        ):
            return problem("找不到这轮对话。", 404)
        try:
            item = dialogue.conversation_record(account.user_id, int(identity))
        except (sqlite3.Error, ValueError):
            return problem("暂时无法读取这轮对话，请稍后再试。", 503)
        scope = values["topic"]
        if item is None or (scope and scope != (item["topic_id"] or "unfiled")):
            return problem("找不到这轮对话。", 404)
        body = (
            '<p><a class="text-link" href="'
            + escape(url(values), quote=True)
            + '">← 返回原来的对话记录</a></p>'
            '<section class="library-card"><p class="eyebrow">一次讨论，一份积累</p><h2>'
            + escape(item["topic_title"] or "未归入学习主题")
            + '</h2><p class="conversation-record-meta">'
            + escape(stamp(item))
            + " · "
            + status(item)
            + '</p><p class="lesson-search-label">这里只回看已有记录。当前学习位置保持不变。</p>'
            + '<a class="button button-outline" href="/web/conversations/'
            + str(item["turn_id"])
            + '/download">下载本轮问答</a>'
            + '<p class="lesson-search-label">保存为可离线阅读的网页，包含本轮问题、已保存回复与当时引用；不调用 AI。</p></section>'
        )
        lower, upper = conversation_date_window(
            values.get("start", ""), values.get("end", "")
        )
        if (lower is not None and item["created_at"] < lower) or (
            upper is not None and item["created_at"] >= upper
        ):
            body += '<p class="lesson-search-label">本轮发起日期不在所选范围内；相邻问答按同一主题连接，可以阅读当前问答或返回原日期结果。</p>'
        query = values["q"]
        if query:
            matches = []
            for key, speaker in (("user_content", "你"), ("assistant_content", "知行")):
                snippets = match_contexts(item[key] or "", query, limit=1)["contexts"]
                matches.extend({"speaker": speaker, **part} for part in snippets)
            body += (
                '<section class="library-card"><h2>关键词附近的对话</h2>'
                + (
                    "".join(excerpt(part, query) for part in matches)
                    or "<p>这轮对话中没有匹配文字，可继续阅读完整记录或返回查找。</p>"
                )
                + "</section>"
            )
        body += (
            '<article class="library-card conversation-record-question"><h2>你当时的问题</h2><div class="conversation-record-text">'
            + search_highlight(item["user_content"], query)
            + "</div></article>"
        )
        body += '<article class="library-card conversation-record-answer"><h2>知行当时的回复</h2>'
        if item["status"] == "complete":
            body += (
                '<div class="markdown-content">'
                + coach_markdown(item["assistant_content"])
                + "</div>"
            )
            for source in item["citations"]:
                body += (
                    '<details class="citation"><summary>当时的引用：'
                    + escape(source["title"] + " · " + source["locator"])
                    + "</summary><p>"
                    + escape(source["excerpt"])
                    + "</p></details>"
                )
        else:
            body += (
                "<p>"
                + (
                    "本轮尚未记录完整回复，可以回到当前对话查看最新状态。"
                    if item["status"] == "pending"
                    else "这轮未取得回复，你当时发送的消息仍保留。"
                )
                + "回看和刷新不会重新发送。</p>"
            )
        body += "</article>"
        if item["lessons"]:
            body += '<section class="library-card"><h2>这轮讨论留下的教案</h2>'
            for lesson in item["lessons"]:
                body += (
                    '<p><a class="text-link" href="/web/knowledge/'
                    + lesson["knowledge_id"]
                    + '">'
                    + escape(lesson["title"])
                    + "</a> · "
                    + (
                        "待你确认的草稿"
                        if lesson["status"] == "pending"
                        else "已保存教案"
                    )
                    + "</p>"
                )
            body += "</section>"
        body += '<nav class="library-paging" aria-label="同一归属的相邻对话">'
        labels = (
            (("previous", "← 该主题上一轮"), ("next", "该主题下一轮 →"))
            if item["topic_id"]
            else (("previous", "← 上一轮未分类记录"), ("next", "下一轮未分类记录 →"))
        )
        for key, label in labels:
            if item["neighbors"][key] is not None:
                body += (
                    '<a href="'
                    + escape(url(values, turn=item["neighbors"][key]), quote=True)
                    + '">'
                    + label
                    + "</a>"
                )
        body += "</nav>"
        if item["topic_id"]:
            identity = item["topic_id"]
            token = library_csrf(
                csrf_key,
                request.cookies.get("coach_login_session", ""),
                "study-open",
                identity,
            )
            body += (
                '<section class="library-card"><h2>从这个主题接着聊</h2><p>点击后恢复该主题当前保存的学习位置，不调用 AI；回到聊天框后，可继续提问或点击续学。历史回复和当时引用保留原样。</p><form method="post" action="/web/studies/'
                + identity
                + '/open"><input type="hidden" name="csrf" value="'
                + token
                + '"><button class="button button-primary" type="submit">回到这个学习主题</button></form></section>'
            )
        else:
            body += '<p class="lesson-search-label">本轮没有可靠的主题归属；可以回到统一对话，说明你想继续讨论的内容。</p>'
        return page("回看一轮对话", body, copy=True)
