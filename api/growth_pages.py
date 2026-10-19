"""Private growth reflection from existing records; no writes or model calls."""

import sqlite3
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse

from api.library_pages import HEADERS
from api.public_pages import _render_layout
from security.login_sessions import signed_in_account
from security.registration_rate_limit import RegistrationRateLimiter


def register_growth_pages(app, accounts, dialogue):
    views = RegistrationRateLimiter(per_client_limit=40, total_limit=400)

    def page(body, code=200):
        content = (
            '<main id="main-content" class="library-space growth-review-space"><nav class="library-tabs" aria-label="工作区入口"><a href="/web/welcome">← 回到对话</a><a href="/web/growth" aria-current="page">成长回顾</a><a href="/web/studies">我的学习</a><a href="/web/conversations">对话记录</a><a href="/web/knowledge">知识资产沉淀</a></nav><h1>成长回顾</h1>'
            + body
            + "</main>"
        )
        return HTMLResponse(
            _render_layout("成长回顾 · 知行", content, signed_in=True),
            status_code=code,
            headers=HEADERS,
        )

    def stamp(value):
        return datetime.fromtimestamp(value, timezone(timedelta(hours=8))).strftime(
            "%Y-%m-%d %H:%M"
        )

    @app.get("/web/growth", include_in_schema=False)
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
            period = request.query_params.get("period", "7")
            if len(request.query_params.getlist("period")) > 1 or period not in {
                "7",
                "30",
                "all",
            }:
                return page(
                    '<p class="form-error-summary" role="alert">请选择最近7天、30天或全部时间。</p><a class="text-link" href="/web/growth">返回成长回顾</a>',
                    400,
                )
            snapshot = dialogue.growth_review(account.user_id, period=period)
        except sqlite3.Error:
            return page(
                '<p class="form-error-summary" role="alert">暂时无法读取成长记录，请稍后再试。</p>',
                503,
            )
        body = '<p class="library-intro">把走过的学习过程看清楚，按自己的节奏继续。不需要打卡或填写评分。</p><nav class="library-tabs" aria-label="回顾时间范围">'
        for value, label in [("7", "最近7天"), ("30", "最近30天"), ("all", "全部时间")]:
            body += (
                '<a href="?period='
                + value
                + '"'
                + (' aria-current="page"' if period == value else "")
                + ">"
                + label
                + "</a>"
            )
        body += '</nav><p class="lesson-revision-note">'
        body += (
            escape(snapshot["start_day"]) + " 至 "
            if snapshot["start_day"]
            else "全部已有记录 · "
        )
        body += (
            escape(snapshot["end_day"])
            + ' · 北京时间，截至本次打开。</p><div class="growth-totals" aria-label="本期记录概览">'
        )
        for key, label in [
            ("completed_turns", "完成对话"),
            ("saved_lessons", "确认教案"),
            ("active_topics", "活跃主题"),
        ]:
            body += (
                '<section class="growth-total"><h2>'
                + label
                + "</h2><p>"
                + str(snapshot[key])
                + "</p></section>"
            )
        body += '</div><p class="lesson-revision-note">这些数字表示实际记录，不代表学习时长、完成程度或掌握水平。</p>'
        if not snapshot["completed_turns"] and not snapshot["saved_lessons"]:
            body += '<section class="library-card"><h2>从一个问题开始</h2><p>这段时间还没有完成对话或确认教案。不必赶进度，可以从今天最想弄懂的一件事开始，也可以切换时间范围看看更早的积累。</p><a class="button button-primary" href="/web/welcome">回到对话</a></section>'
        body += '<div class="growth-columns"><section class="library-card"><h2>近期讨论</h2>'
        for item in snapshot["recent_turns"]:
            body += (
                '<article class="growth-entry"><p class="conversation-record-meta">'
                + escape(stamp(item["completed_at"]))
                + " · "
                + escape(item["topic_title"] or "未归入学习主题")
                + '</p><h3><a href="/web/conversations/'
                + str(item["turn_id"])
                + '">'
                + escape(item["question"])
                + ("…" if item["shortened"] else "")
                + "</a></h3></article>"
            )
        if not snapshot["recent_turns"]:
            body += "<p>本期还没有已完成的对话。</p>"
        body += '<a class="text-link" href="/web/conversations">查看全部对话记录 →</a></section><section class="library-card"><h2>本期确认的教案</h2>'
        for item in snapshot["recent_lessons"]:
            body += (
                '<article class="growth-entry"><p class="conversation-record-meta">'
                + escape(stamp(item["saved_at"]))
                + " · "
                + escape(item["topic"])
                + '</p><h3><a href="/web/knowledge/'
                + item["knowledge_id"]
                + '">'
                + escape(item["title"])
                + "</a></h3></article>"
            )
        if not snapshot["recent_lessons"]:
            body += "<p>本期还没有确认保存的教案，已有草稿可以随时继续整理。</p>"
        body += '<a class="text-link" href="/web/knowledge">调阅全部已保存教案 →</a></section></div><section class="library-card"><h2>正在积累的主题</h2><p class="lesson-revision-note">本期有已完成对话的学习主题，按最近讨论排列，最多展示5个。</p>'
        for item in snapshot["recent_topics"]:
            target = "/web/conversations?" + urlencode({"topic": item["topic_id"]})
            body += (
                '<article class="growth-entry"><h3><a href="'
                + escape(target, quote=True)
                + '">'
                + escape(item["title"])
                + "</a></h3><p>"
                + str(item["completed_turns"])
                + " 轮已完成对话 · 最近 "
                + escape(stamp(item["last_completed_at"]))
                + "</p></article>"
            )
        if not snapshot["recent_topics"]:
            body += "<p>本期还没有归入现有学习主题的已完成对话。自由交流同样会保留在对话记录中。</p>"
        body += '<div class="library-actions"><a class="button button-primary" href="/web/studies">继续我的学习</a><a class="button button-outline" href="/web/knowledge-favorites">重温常用教案</a></div></section><details class="library-card"><summary>这些记录如何计算</summary><p>时间范围含今天，以北京时间零点为起点。完成对话按实际完成时间计入；失败和等待中的消息不计入，明确保存记忆等已完成交流会保留在对话记录中。教案按首次确认保存时间计入，草稿和已移出草稿不计入；修改标题、修订、收藏不会重复增加数量。教案名称使用当前版本。</p><p>主题只统计归入现有本人主题的已完成对话；未分类的历史不会被自动归档。各列表最多展示最近5项，完整内容可从对应目录调阅，目录另有自己的查找范围。打开回顾只读取已有记录，不改变学习位置、不调用AI；点击续学入口后，由你继续选择下一步。</p></details>'
        return page(body)
