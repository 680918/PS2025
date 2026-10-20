"""A bounded, standalone copy of one already stored question and answer."""

from datetime import datetime, timedelta, timezone
from html import escape

from api.asset_export import STYLE
from api.coach_markdown import coach_markdown


MAX_TEXT = 250000
MAX_BYTES = 2 * 1024**2
LOCAL_ZONE = timezone(timedelta(hours=8))


def conversation_document(item):
    """Return UTF-8 HTML and a safe basename; no live links or model calls."""
    state = item["status"]
    if state not in {"complete", "pending", "failed"}:
        raise ValueError("对话状态暂时无法读取。")
    title = item["topic_title"] or "未归入学习主题"
    question = item["user_content"]
    answer = (item["assistant_content"] or "") if state == "complete" else ""
    sources = item["citations"] if state == "complete" else []
    texts = [title, question, answer]
    texts.extend(
        source[key] for source in sources for key in ("title", "locator", "excerpt")
    )
    if sum(len(text) for text in texts) > MAX_TEXT:
        raise ValueError("这轮内容较多，请使用完整学习资料导出。")
    created = datetime.fromtimestamp(item["created_at"], LOCAL_ZONE)
    label = {"complete": "已回复", "pending": "尚未完成", "failed": "未取得回复"}[state]
    body = (
        '<p class="meta">知行 · 单轮问答离线副本</p><h1>'
        + escape(title)
        + '</h1><p class="meta">'
        + created.strftime("%Y-%m-%d %H:%M · 北京时间")
        + " · "
        + label
        + '</p><p class="note">主题名称取下载时的名称；问答与引用取已保存记录。此文件仅含这一轮问答和引用，不含教案或书籍全文。离线副本不会随后更新。</p>'
        '<article class="user"><h2>你当时的问题</h2><div class="plain">'
        + escape(question)
        + "</div></article><article><h2>知行当时的回复</h2>"
    )
    if state == "complete":
        body += coach_markdown(answer)
    else:
        body += (
            "<p>"
            + (
                "下载时本轮尚未记录完整回复。可回到知行查看最新状态。"
                if state == "pending"
                else "这轮未取得回复，你当时发送的消息仍保留。"
            )
            + "下载不会重新发送，也不会调用 AI。</p>"
        )
    body += "</article>"
    if sources:
        body += '<section class="card"><h2>当时保存的引用</h2>'
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
        "<title>问答 · "
        + escape(title)
        + "</title><style>"
        + STYLE
        + "</style></head><body><main>"
        + body
        + "</main></body></html>"
    ).encode("utf-8")
    if len(document) > MAX_BYTES:
        raise ValueError("这轮文件较大，请使用完整学习资料导出。")
    # The file name never incorporates user-supplied title or question text.
    name = (
        "知行-问答-" + created.strftime("%Y%m%d") + "-" + str(item["turn_id"]) + ".html"
    )
    return document, name
