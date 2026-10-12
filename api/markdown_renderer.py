import re

from markdown_it import MarkdownIt


_markdown = MarkdownIt(
    "commonmark",
    {
        "html": False,
    },
)


def _normalize_escaped_markdown(content):
    text = str(content)

    # Escaped Markdown headings:
    # \## Title -> ## Title
    text = re.sub(
        r"(?m)^\\(#{1,6})(?=\s)",
        r"\1",
        text,
    )

    # Escaped bold markers:
    # \*\*text\*\* -> **text**
    text = text.replace(
        r"\*\*",
        "**",
    )

    # Escaped inline-code markers:
    # \`code\` -> `code`
    text = text.replace(
        r"\`",
        "`",
    )

    return text


def render_safe_markdown(content):
    if content is None:
        return ""

    normalized_content = _normalize_escaped_markdown(
        content,
    )

    return _markdown.render(normalized_content)
