from html.parser import HTMLParser

import pytest

from api import lesson_export
from api.lesson_export import lesson_document
from coach.unit_lessons import unit_scope_text


@pytest.fixture
def item():
    return {
        "knowledge_id": "a" * 32,
        "status": "saved",
        "revision": 2,
        "title": "复习 <script>alert(1)</script>",
        "topic": "阅读 & 练习",
        "content": '## 核心知识\n\n| 方法 | 用途 |\n| --- | --- |\n| 回想 | 巩固 |\n\n~~~python\nif ready:\n    print("复习")\n~~~\n\n<img src=x onerror=alert(1)>\n\n[远程链接](https://example.com)\n\n![图](https://example.com/a.png)',
        "revised_at": 1704067200,
        "citations": [
            {
                "title": "原书 <img>",
                "locator": "第 2 页",
                "excerpt": "<script>原文</script>\n下一行",
            }
        ],
    }


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags, self.unsafe = [], []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        if tag in {
            "script",
            "img",
            "iframe",
            "a",
            "form",
            "link",
            "object",
            "embed",
        } or any(key.startswith("on") for key, _ in attrs):
            self.unsafe.append(tag)


def test_readable_document_keeps_metadata_table_code_and_escaped_sources_without_active_content(
    item,
):
    content, name = lesson_document(item)
    text = content.decode("utf-8")
    tags = Tags(text)
    assert name == "知行-教案-" + "a" * 32 + "-v2.html"
    assert "script" not in name and "<script>" not in text
    assert "<table>" in text and "<pre " in text and "<code>" in text
    assert "    print(&quot;复习&quot;)" in text
    assert "原书 &lt;img&gt; · 第 2 页" in text
    assert "&lt;script&gt;原文&lt;/script&gt;\n下一行" in text
    assert "第 2 版" in text and "2024-01-01 08:00 · 北京时间" in text
    assert "阅读 &amp; 练习" in text
    assert "后续修订不会自动更新此文件" in text
    assert "最初整理时的引用" in text
    assert (
        "default-src 'none'" in text and 'name="referrer" content="no-referrer"' in text
    )
    assert tags.unsafe == [] and text.count("<h1>") == 1
    assert "../../" not in text and "/web/" not in text


def test_generation_scope_is_preserved_as_plain_text_and_not_invented(item):
    content, _ = lesson_document(item)
    assert "生成时的整理范围" not in content.decode()
    scope = {
        "material_title": "<书籍>",
        "unit_title": "第一单元",
        "range": "第 2–5 页",
        "explained": 3,
        "total": 4,
        "batch": 1,
        "batch_count": 2,
        "sources": [{"locator": "第2页"}],
    }
    item["unit_summary"] = scope
    content, _ = lesson_document(item)
    assert "生成时的整理范围" in content.decode()
    assert "书籍：&lt;书籍&gt;" in content.decode()
    assert "3 / 4 段" in content.decode() and "第 1 / 2 批" in content.decode()
    assert unit_scope_text(scope).replace("<书籍>", "&lt;书籍&gt;") in content.decode()


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "pending"),
        ("status", "dismissed"),
        ("knowledge_id", "../private"),
        ("revision", 0),
        ("revision", True),
        ("revision", 1000000001),
    ],
)
def test_only_saved_safe_identity_and_current_version_are_supported(item, field, value):
    item[field] = value
    with pytest.raises(ValueError):
        lesson_document(item)


def test_source_length_is_bounded_before_markdown_rendering(item, monkeypatch):
    monkeypatch.setattr(lesson_export, "MAX_TEXT", 10)
    monkeypatch.setattr(
        lesson_export,
        "coach_markdown",
        lambda *_: pytest.fail("Oversize text must not be rendered"),
    )
    with pytest.raises(ValueError, match="内容较多"):
        lesson_document(item)


def test_encoded_file_size_is_bounded_and_empty_citations_work(item, monkeypatch):
    item["citations"] = []
    item["revised_at"] = None
    content, _ = lesson_document(item)
    assert "未记录" in content.decode() and "最初整理时的引用" not in content.decode()
    monkeypatch.setattr(lesson_export, "MAX_BYTES", len(content) - 1)
    with pytest.raises(ValueError, match="文件较大"):
        lesson_document(item)
