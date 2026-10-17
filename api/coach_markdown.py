"""Shared, local Markdown presentation for chat history and lesson previews."""

import re
from html import escape

from markdown_it import MarkdownIt


def _normalize(content):
    # Repair escaped formatting from model replies, preserving literal code.
    lines = []
    fence = None
    for line in str(content).splitlines(keepends=True):
        marker = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker[1]
            if fence is None:
                fence = run
            elif (
                run[0] == fence[0]
                and len(run) >= len(fence)
                and not line[marker.end() :].strip()
            ):
                fence = None
            lines.append(line)
            continue
        if fence or line.startswith(("    ", "\t")):
            lines.append(line)
            continue
        pieces = re.split(r"(`+[^`]*`+)", line)
        for index in range(0, len(pieces), 2):
            pieces[index] = pieces[index].replace(r"\*\*", "**")
        line = "".join(pieces)
        lines.append(re.sub(r"^\\(#{1,6})(?=\s)", r"\1", line))
    return "".join(lines)


def _fence(tokens, index, options, env):
    token = tokens[index]
    language = token.info.strip().split(maxsplit=1)[0] if token.info.strip() else ""
    language = re.sub(r"[^\w+#.-]", "", language)[:32]
    label = "代码" + (" · " + language if language else "")
    return (
        '<div class="code-block"><div class="code-block-label">'
        + escape(label)
        + '</div><pre tabindex="0" aria-label="代码，可横向滚动"><code>'
        + escape(token.content)
        + "</code></pre></div>\n"
    )


_markdown = (
    MarkdownIt("commonmark", {"html": False})
    .enable("table")
    .disable(["image", "link", "autolink"])
)
_markdown.renderer.rules["fence"] = _fence
_markdown.renderer.rules["table_open"] = lambda *args: (
    '<div class="markdown-table-scroll" role="region" aria-label="表格，可横向滚动" tabindex="0"><table>\n'
)
_markdown.renderer.rules["table_close"] = lambda *args: "</table></div>\n"
_markdown.renderer.rules["th_open"] = lambda *args: '<th scope="col">'
_markdown.renderer.rules["td_open"] = lambda *args: "<td>"


def coach_markdown(content):
    return _markdown.render(_normalize(content)) if content is not None else ""
