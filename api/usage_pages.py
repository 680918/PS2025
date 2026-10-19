"""Owned usage totals and limits; changing limits is a local operator action."""

import sqlite3
from html import escape

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse
from api.library_pages import HEADERS
from api.public_pages import _render_layout
from coach.ai_usage import usage_message
from security.login_sessions import signed_in_account
from security.registration_rate_limit import RegistrationRateLimiter


def register_usage_pages(app, accounts, dialogue):
    views = RegistrationRateLimiter(per_client_limit=40, total_limit=400)

    def page(body, code=200):
        content = (
            '<main id="main-content" class="library-space"><nav class="library-tabs" aria-label="工作区入口"><a href="/web/welcome">← 回到对话</a><a href="/web/usage">AI 用量</a><a href="/web/knowledge">知识资产沉淀</a><a href="/web/materials">资料与书籍</a></nav><h1>AI 用量与使用上限</h1>'
            + body
            + "</main>"
        )
        return HTMLResponse(
            _render_layout("AI 用量 · 知行", content, signed_in=True),
            status_code=code,
            headers=HEADERS,
        )

    @app.get("/web/usage", include_in_schema=False)
    def index(request: Request):
        wait = views.admit(request.client.host if request.client else "unknown")
        if wait:
            response = page('<p role="alert">查看较频繁，请稍后再试。</p>', 429)
            response.headers["Retry-After"] = str(wait)
            return response
        try:
            account = signed_in_account(
                accounts, request.cookies.get("coach_login_session")
            )
            if account is None:
                return RedirectResponse("/web/login", status_code=303, headers=HEADERS)
            snapshot = dialogue.ai_usage(account.user_id)
        except sqlite3.Error:
            return page('<p role="alert">暂时无法读取用量，请稍后再试。</p>', 503)
        body = (
            '<p class="library-intro">了解自己的使用情况，按节奏交流与积累。</p><section class="library-card"><h2>今天 · '
            + escape(snapshot["day"])
            + '</h2><p class="usage-total">已受理 <strong>'
            + str(snapshot["used"])
            + "</strong> / "
            + str(snapshot["user_limit"])
            + " 次</p><p>北京时间每日零点按新一天计算，重启服务不会清零。本空间另设共同额度。</p>"
        )
        if snapshot["reason"]:
            body += (
                '<p class="form-error-summary" role="status">'
                + escape(usage_message(snapshot, rejected=False))
                + "</p>"
            )
        body += (
            '</section><section class="library-card markdown-content"><h2>最近七天</h2>'
        )
        if snapshot["recent"]:
            body += '<div class="markdown-table-scroll" role="region" aria-label="近七天请求记录，可横向滚动" tabindex="0"><table><thead><tr><th scope="col">日期</th><th scope="col">用途</th><th scope="col">已受理次数</th></tr></thead><tbody>'
            for item in snapshot["recent"]:
                body += (
                    "<tr><td>"
                    + escape(item["day"])
                    + "</td><td>"
                    + (
                        "聊天、续学与对话教案"
                        if item["kind"] == "dialogue"
                        else "书籍单元教案"
                    )
                    + "</td><td>"
                    + str(item["count"])
                    + "</td></tr>"
                )
            body += "</tbody></table></div>"
        else:
            body += "<p>这里还没有受理记录。浏览已有内容不占用次数。</p>"
        body += '</section><section class="library-card"><h2>这些次数如何计算</h2><p>聊天、继续学习、选段讲解、对话中整理教案和书籍单元整理共用每日次数。一次受理记一次，重复提交同一请求不重复计数。</p><p>次数从本功能启用后开始记录，包含模拟回复与失败、中断或未送达的尝试，保守保留已受理次数；它不是实际账单或费用金额。真实收费以 AI 服务商记录为准。</p><p>阅读、查找、上传、教案手动修订、确认保存、导出，以及明确保存学习记忆不占用 AI 次数。达到上限仍可使用这些功能。</p><details><summary>本机试用说明</summary><p>上限由本机维护者通过终端调整，网页不能提高额度。这里只统计此成长空间的数据目录，其他应用或目录不共享次数。备份恢复后使用备份时保留的记录和上限。</p></details></section>'
        return page(body)
