"""Private book-reading presentation; original pages and OCR are distinct."""

from html import escape

from fastapi.responses import HTMLResponse

from api.public_pages import _render_layout


def ocr_panel(base, token, total):
    return (
        '<section id="book-ocr" class="book-ocr-panel" aria-labelledby="ocr-title" hidden data-status-url="'
        + base
        + '/ocr" data-csrf="'
        + escape(token, quote=True)
        + '"><h2 id="ocr-title">扫描文字识别 · 本地核对</h2>'
        + "<p>在本机识别当前页，核对并保存后才供 Coach 引用；不调用付费 AI。适合横排简体、繁体中文和英文，竖排、模糊扫描或复杂排版可能有误。</p>"
        + '<label for="ocr-language">识别语言</label><select id="ocr-language"><option value="chi_sim">简体中文 + 英文</option><option value="chi_tra">繁体中文 + 英文</option></select>'
        + '<form id="ocr-range-form" class="ocr-range-form"><div><label for="ocr-range-start">开始 PDF 文件页</label><input id="ocr-range-start" type="number" min="1" max="'
        + str(total)
        + '" step="1" value="1" name="first" required disabled></div><div><label for="ocr-range-end">结束 PDF 文件页</label><input id="ocr-range-end" type="number" min="1" max="'
        + str(total)
        + '" step="1" value="'
        + str(min(5, total))
        + '" name="last" required disabled></div><button id="ocr-range-go" class="button button-primary" type="submit" disabled>开始识别所选范围</button></form>'
        + '<p class="ocr-note">每批最多 5 页，按文件页码连续处理。已有文字自动跳过；新结果只留在本页，核对后逐页保存。取消保留已完成结果，失败页不会自动重试。</p>'
        + '<p id="ocr-status" role="status" aria-live="polite">请在阅读工具栏点击“识别当前页”。</p>'
        + '<button id="ocr-cancel" class="button button-outline" type="button" hidden>取消识别</button>'
        + '<p id="ocr-queue-summary" class="ocr-note" aria-live="polite"></p><div id="ocr-results" class="ocr-results" role="group" aria-label="本批逐页识别结果"></div>'
        + '<label for="ocr-text" id="ocr-result-label">识别结果（保存前可修改）</label><textarea id="ocr-text" rows="10" maxlength="40000" disabled></textarea>'
        + '<p id="ocr-confidence" class="ocr-note"></p><div class="library-actions">'
        + '<button id="ocr-original" class="button button-outline" type="button" disabled>回到这一页核对</button>'
        + '<button id="ocr-save" class="button button-primary" type="button" disabled>核对无误，保存此页文字</button>'
        + '<button id="ocr-discard" class="button button-outline" type="button" hidden>放弃本批全部未保存结果</button>'
        + '<button id="ocr-result-previous" class="button button-outline" type="button" disabled>上一页结果</button><button id="ocr-result-next" class="button button-outline" type="button" disabled>下一页结果</button>'
        + '<a id="ocr-study" class="button button-outline" hidden>选段学习这页文字</a></div>'
        + '<p class="ocr-note">保存会增加这本书的可引用文字；原始 PDF 不变。已有文字的页面不重复写入或覆盖，避免改动历史引用。</p></section>'
    )


def extraction_notice(item):
    if item["kind"] != "pdf":
        return ""
    readable, total = item["readable_pages"], item["page_count"]
    if readable == total:
        return (
            '<p class="extraction-notice">文字已提取 · '
            + str(total)
            + " / "
            + str(total)
            + " 页。阅读原页不调用 AI。</p>"
        )
    return (
        '<p class="extraction-notice extraction-incomplete"><strong>文字提取不完整 · '
        + str(readable)
        + " / "
        + str(total)
        + " 页，"
        + str(item["char_count"])
        + " 字。</strong>未提取文字的页面仍可在“阅读全书”查看原页；这些页面可能是扫描图片，尚需文字识别（OCR）。可点击“识别当前页”，核对并保存后供 Coach 引用。未识别的正文仍不能据此逐章讲解。</p>"
    )


def reader_response(
    item,
    total,
    number,
    *,
    ocr_csrf="",
    bookmark_csrf="",
    bookmark=None,
    learning_locator="",
):
    base = "/web/materials/" + item["material_id"]
    pdf = item["kind"] == "pdf"
    bookmark = bookmark or {"page": 1, "revision": 0}
    position_panel = (
        '<section class="reader-continuity" aria-label="阅读与学习位置"><p><strong>阅读位置</strong> · <span id="reader-saved-summary">'
        + (
            "已记住第 " + str(bookmark["page"]) + " 页"
            if bookmark["revision"]
            else "尚未记录"
        )
        + "</span>；停留后自动记住，重新打开可续读。</p><p><strong>本书选段学习位置</strong> · "
        + escape(learning_locator or "尚未选择文字片段")
        + "。阅读页与学习位置分开；都不表示已经掌握。</p>"
        + '<form id="reader-bookmark" method="post" action="'
        + base
        + '/read/position">'
        + '<input type="hidden" name="csrf" value="'
        + escape(bookmark_csrf, quote=True)
        + '">'
        + '<input type="hidden" name="page" value="'
        + str(number)
        + '">'
        + '<input type="hidden" name="revision" value="'
        + str(bookmark["revision"])
        + '">'
        + '<a class="button button-outline" href="'
        + base
        + '/plan">本书学习目录</a></form>'
        + "<p>阅读不调用 AI；点击学习先预览文字，明确发送问题才调用。</p></section>"
    )
    body = (
        '<main id="main-content" class="book-reading-space"><nav class="library-tabs" aria-label="阅读导航"><a href="/web/materials">← 资料与书籍</a><a href="/web/welcome">回到对话</a><a href="'
        + base
        + '">文字选段与提问</a><a href="'
        + base
        + '/original">下载原件</a></nav><h1>'
        + escape(item["title"])
        + '</h1><p class="reader-intro">阅读全书 · '
        + (
            "直接阅读原始 PDF，共 "
            + str(total)
            + " 页。向下滚动或输入页码阅读，无需先识别文字；文件页码可能不同于书内印刷页码。"
            if pdf
            else "文字连续阅读；阅读页按约 2400 字划分，保留原文换行。"
        )
        + "</p>"
        + '<section id="book-reader" data-kind="'
        + escape(item["kind"], quote=True)
        + '" data-total="'
        + str(total)
        + '" data-initial="'
        + str(number)
        + '" data-source="'
        + base
        + '/original" data-text-pages="'
        + base
        + '/read/pages" data-saved-page="'
        + str(bookmark["page"] if bookmark["revision"] else 0)
        + '" data-state="loading">'
        + position_panel
        + '<div class="reader-toolbar"><form id="reader-previous-form" class="reader-turn" method="get"><input id="reader-previous-page" type="hidden" name="page" value="'
        + str(max(1, number - 1))
        + '"><button class="button button-outline" id="reader-previous" type="submit"'
        + (' disabled title="已到第一页"' if number == 1 else "")
        + '>上一页</button></form><form id="reader-locate" method="get"><label for="reader-page-number">跳到阅读页</label><input id="reader-page-number" name="page" type="number" min="1" max="'
        + str(total)
        + '" value="'
        + str(number)
        + '" required><span> / '
        + str(total)
        + '</span><button class="button button-outline" type="submit">前往</button></form><form id="reader-next-form" class="reader-turn" method="get"><input id="reader-next-page" type="hidden" name="page" value="'
        + str(min(total, number + 1))
        + '"><button class="button button-outline" id="reader-next" type="submit"'
        + (' disabled title="已到最后一页"' if number == total else "")
        + ">下一页</button></form>"
        + (
            '<label for="reader-zoom">显示大小</label><select id="reader-zoom"><option value="1">适合宽度</option><option value="1.25">放大 125%</option><option value="1.5">放大 150%</option></select>'
            if pdf
            else ""
        )
        + (
            '<button id="ocr-start" class="button button-outline" type="button" disabled>识别当前页</button><button id="ocr-range-open" class="button button-outline" type="button" disabled>识别一段页码</button><button id="ocr-view" class="button button-outline" type="button" hidden>查看识别结果</button>'
            if pdf
            else ""
        )
        + '<a id="reader-study" class="button button-primary" href="'
        + base
        + "/read/learn?page="
        + str(number)
        + '">学习当前页</a><button class="button button-outline" form="reader-bookmark" type="submit">记住当前页</button>'
        + '<span class="reader-position-status">选段学习 · '
        + escape(learning_locator or "尚未选择片段")
        + '</span><p id="bookmark-status" class="reader-position-status" role="status" aria-live="polite">'
        + (
            "已记住阅读第 " + str(bookmark["page"]) + " 页。"
            if bookmark["revision"]
            else "尚未记录阅读位置。"
        )
        + "停留后自动记住，与学习进度分开。</p></div>"
        + (
            '<p class="reader-alternative">书页未显示？<a id="reader-direct" class="button button-outline" href="'
            + base
            + "/read/pdf#page="
            + str(number)
            + '" target="_blank" rel="noopener noreferrer">直接打开原始 PDF</a><span>浏览器自带阅读器；知行翻页和 Enter 快捷键请在本页使用。</span></p>'
            + '<details class="reader-extraction"><summary>Coach 的文字依据 · '
            + str(item["readable_pages"])
            + " / "
            + str(total)
            + " 页（不影响原书阅读）</summary>"
            + extraction_notice(item)
            + "</details>"
            if pdf
            else ""
        )
        + (ocr_panel(base, ocr_csrf, total) if pdf else "")
        + '<p id="reader-shortcuts" class="reader-shortcuts">阅读时按 Enter 到下一页；输入框中保留原有输入操作。</p><progress id="reader-progress" aria-label="原书加载进度"></progress><p id="reader-status" role="status" aria-live="polite">正在打开原书，较大文件首次加载需要一点时间…</p><button id="reader-retry" class="button button-outline" type="button" hidden>重试当前页</button><div id="reader-pages" aria-label="全书连续阅读页面" aria-describedby="reader-shortcuts"></div>'
        + '<noscript><p>连续阅读需要开启 JavaScript。也可以<a class="text-link" href="'
        + base
        + '/original">下载原件阅读</a>。</p></noscript></section>'
        + '<link rel="stylesheet" href="/static/vendor/pdfjs/web/pdf_viewer.css"><script type="module" src="/static/book-reader.mjs?v=20261022-ocr-range"></script></main>'
    )
    return HTMLResponse(
        _render_layout("阅读全书 · 知行", body, signed_in=True),
        headers={
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Content-Security-Policy": "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self'; connect-src 'self'; worker-src 'self'; img-src 'self' data: blob:; font-src 'self' blob:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
        },
    )
