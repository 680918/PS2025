"""One bounded, self-contained reading copy of a confirmed lesson."""

import re
from datetime import datetime, timedelta, timezone
from html import escape

from api.asset_export import STYLE
from api.coach_markdown import coach_markdown
from coach.unit_lessons import unit_scope_text

MAX_TEXT = 250000
MAX_BYTES = 2 * 1024**2
LOCAL_ZONE = timezone(timedelta(hours=8))


def lesson_document(item):
    """Return UTF-8 HTML and a safe filename, without live links or AI calls."""
    identity, revision = item["knowledge_id"], item["revision"]
    if (
        item["status"] != "saved"
        or re.fullmatch(r"[a-f0-9]{32}", identity) is None
        or type(revision) is not int
        or not 1 <= revision <= 1000000000
    ):
        raise ValueError("请从已保存教案下载当前阅读版。")
    title, topic, content = item["title"], item["topic"], item["content"]
    sources = item["citations"]
    scope = unit_scope_text(item["unit_summary"]) if item.get("unit_summary") else ""
    texts = [title, topic, content, scope]
    texts.extend(
        source[key] for source in sources for key in ("title", "locator", "excerpt")
    )
    if sum(len(text) for text in texts) > MAX_TEXT:
        raise ValueError("这份教案内容较多，请使用完整学习资料导出。")
    stamp = item["revised_at"]
    date = (
        datetime.fromtimestamp(stamp, LOCAL_ZONE).strftime("%Y-%m-%d %H:%M · 北京时间")
        if stamp
        else "未记录"
    )
    body = (
        '<p class="meta">知行 · 已保存教案离线阅读版</p><h1>'
        + escape(title)
        + '</h1><p class="meta">第 '
        + str(revision)
        + " 版 · "
        + date
        + '</p><p class="meta">原学习主题：'
        + escape(topic)
        + '</p><p class="note">这是下载时的当前教案副本，后续修订不会自动更新此文件。引用保留最初整理时的参考；修订内容是否得到原书支持，仍需自行核对。</p>'
    )
    if scope:
        body += (
            '<section class="card"><h2>生成时的整理范围</h2><div class="plain">'
            + escape(scope)
            + "</div></section>"
        )
    body += '<article aria-label="教案正文">' + coach_markdown(content) + "</article>"
    if sources:
        body += '<section class="card"><h2>最初整理时的引用</h2>'
        for number, source in enumerate(sources, 1):
            body += (
                "<h3>"
                + str(number)
                + ". "
                + escape(source["title"] + " · " + source["locator"])
                + '</h3><div class="citation">'
                + escape(source["excerpt"])
                + "</div>"
            )
        body += "</section>"
    document = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="referrer" content="no-referrer">'
        "<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'\">"
        "<title>教案 · "
        + escape(title)
        + "</title><style>"
        + STYLE
        + "</style></head><body><main>"
        + body
        + "</main></body></html>"
    ).encode("utf-8")
    if len(document) > MAX_BYTES:
        raise ValueError("这份教案文件较大，请使用完整学习资料导出。")
    return document, "知行-教案-" + identity + "-v" + str(revision) + ".html"
