from api.markdown_renderer import render_safe_markdown


def test_render_safe_markdown_should_render_common_markdown():
    result = render_safe_markdown(
        """
## 本次学习定位

这是 **Tool Calling** 学习任务。

请实现 `save_note(content)`。
"""
    )

    assert "<h2>本次学习定位</h2>" in result
    assert "<strong>Tool Calling</strong>" in result
    assert "<code>save_note(content)</code>" in result


def test_render_safe_markdown_should_escape_raw_html():
    result = render_safe_markdown('<script>alert("xss")</script>')

    assert "<script>" not in result
    assert "&lt;script&gt;" in result


def test_render_safe_markdown_should_handle_none():
    assert render_safe_markdown(None) == ""


def test_render_safe_markdown_should_normalize_escaped_markdown():
    result = render_safe_markdown(
        r"""
\## 本次学习定位

这是 \*\*Tool Calling\*\* 学习任务。

请实现 \`save_note(content)\`。
"""
    )

    assert "<h2>本次学习定位</h2>" in result
    assert "<strong>Tool Calling</strong>" in result
    assert "<code>save_note(content)</code>" in result

    assert r"\##" not in result
    assert r"\*\*" not in result
