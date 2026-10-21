"""Private book-reading presentation; original pages and OCR are distinct."""

from html import escape

from fastapi.responses import HTMLResponse

from api.public_pages import _render_layout


def ocr_panel(base, token):
    return (
        '<section id="book-ocr" class="book-ocr-panel" aria-labelledby="ocr-title" hidden data-status-url="'
        + base
        + '/ocr" data-csrf="'
        + escape(token, quote=True)
        + '"><h2 id="ocr-title">扫描文字识别 · 本地核对</h2>'
        + "<p>在本机识别当前页，核对并保存后才供 Coach 引用；不调用付费 AI。适合横排简体、繁体中文和英文，竖排、模糊扫描或复杂排版可能有误。</p>"
        + '<label for="ocr-language">识别语言</label><select id="ocr-language"><option value="chi_sim">简体中文 + 英文</option><option value="chi_tra">繁体中文 + 英文</option></select>'
        + '<p id="ocr-status" role="status" aria-live="polite">请在阅读工具栏点击“识别当前页”。</p>'
        + '<button id="ocr-cancel" class="button button-outline" type="button" hidden>取消识别</button>'
        + '<label for="ocr-text" id="ocr-result-label">识别结果（保存前可修改）</label><textarea id="ocr-text" rows="10" maxlength="40000" disabled></textarea>'
        + '<p id="ocr-confidence" class="ocr-note"></p><div class="library-actions">'
        + '<button id="ocr-original" class="button button-outline" type="button" disabled>回到这一页核对</button>'
        + '<button id="ocr-save" class="button button-primary" type="button" disabled>核对无误，保存此页文字</button>'
        + '<button id="ocr-discard" class="button button-outline" type="button" hidden>放弃这次未保存结果</button>'
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


def reader_response(item, total, number, *, ocr_csrf=""):
    base = "/web/materials/" + item["material_id"]
    pdf = item["kind"] == "pdf"
    body = (
        '<main id="main-content" class="book-reading-space"><nav class="library-tabs" aria-label="阅读导航"><a href="/web/materials">← 资料与书籍</a><a href="/web/welcome">回到对话</a><a href="'
        + base
        + '">文字选段与提问</a><a href="'
        + base
        + '/original">下载原件</a></nav><h1>'
        + escape(item["title"])
        + '</h1><p class="reader-intro">阅读全书 · '
        + (
            "PDF 原始页面，连续向下滚动；文件页码可能不同于书内印刷页码。"
            if pdf
            else "文字连续阅读；阅读页按约 2400 字划分，保留原文换行。"
        )
        + "</p>"
        + extraction_notice(item)
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
        + '/read/pages">'
        + '<div class="reader-toolbar"><button class="button button-outline" id="reader-previous" type="button" disabled>上一页</button><form id="reader-locate" method="get"><label for="reader-page-number">跳到阅读页</label><input id="reader-page-number" name="page" type="number" min="1" max="'
        + str(total)
        + '" value="'
        + str(number)
        + '" required><span> / '
        + str(total)
        + '</span><button class="button button-outline" type="submit">前往</button></form><button class="button button-outline" id="reader-next" type="button" disabled>下一页</button>'
        + (
            '<label for="reader-zoom">显示大小</label><select id="reader-zoom"><option value="1">适合宽度</option><option value="1.25">放大 125%</option><option value="1.5">放大 150%</option></select>'
            if pdf
            else ""
        )
        + (
            '<button id="ocr-start" class="button button-outline" type="button" disabled>识别当前页</button><button id="ocr-view" class="button button-outline" type="button" hidden>查看识别结果</button>'
            if pdf
            else ""
        )
        + "</div>"
        + (ocr_panel(base, ocr_csrf) if pdf else "")
        + '<p id="reader-status" role="status" aria-live="polite">正在准备阅读页面…</p><button id="reader-retry" class="button button-outline" type="button" hidden>重试当前页</button><div id="reader-pages" aria-label="全书连续阅读页面"></div>'
        + '<noscript><p>连续阅读需要开启 JavaScript。也可以<a class="text-link" href="'
        + base
        + '/original">下载原件阅读</a>。</p></noscript></section>'
        + '<link rel="stylesheet" href="/static/vendor/pdfjs/web/pdf_viewer.css"><script type="module" src="/static/book-reader.mjs"></script></main>'
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
