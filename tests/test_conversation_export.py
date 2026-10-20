from copy import deepcopy
from html.parser import HTMLParser

import pytest

from api import conversation_export as export


def record(**changes):
    return {
        "turn_id": 7,
        "created_at": 0,
        "topic_title": "循序学习",
        "status": "complete",
        "user_content": "请给我一个例子。\n保留第二行。",
        "assistant_content": '## 用例子理解\n\n| 名称 | 方法 |\n| --- | --- |\n| 复习 | 回想 |\n\n```python\nif ready:\n    print("练习")\n```',
        "citations": [
            {"title": "原来的书", "locator": "第 3 页", "excerpt": "先回想。\n再核对。"}
        ],
        "nonce": "NEVER_EXPORT_NONCE",
        "user_id": "NEVER_EXPORT_USER",
        "lessons": [{"title": "NEVER_EXPORT_LESSON"}],
        "neighbors": {"next": 8},
        **changes,
    }


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def test_standalone_html_preserves_chinese_tables_code_sources_and_explicit_fields():
    item = record()
    before = deepcopy(item)
    content, name = export.conversation_document(item)
    html = content.decode("utf-8")
    assert name == "知行-问答-19700101-7.html"
    assert "1970-01-01 08:00 · 北京时间" in html
    assert "<h2>用例子理解</h2>" in html and "<table>" in html
    assert "    print(&quot;练习&quot;)" in html and "代码 · python" in html
    assert "先回想。\n再核对。" in html and "第 3 页" in html
    assert "保留第二行。" in html and "离线副本不会随后更新" in html
    assert all(
        secret not in html
        for secret in ["NEVER_EXPORT_NONCE", "NEVER_EXPORT_USER", "NEVER_EXPORT_LESSON"]
    )
    assert item == before
    assert export.conversation_document(item) == (content, name)
    assert all(
        tag not in {"a", "img", "script", "form", "iframe", "link"}
        for tag, attrs in Tags(html).tags
    )
    assert "default-src 'none'" in html and "<style>" in html


@pytest.mark.parametrize(
    "state,label", [("pending", "尚未完成"), ("failed", "未取得回复")]
)
def test_unfinished_records_never_include_unconfirmed_answer_or_citations(state, label):
    item = record(
        status=state,
        assistant_content="UNCONFIRMED_ANSWER",
        citations=[{"bad": "UNCONFIRMED_SOURCE"}],
    )
    content, _ = export.conversation_document(item)
    text = content.decode()
    assert label in text and "UNCONFIRMED" not in text
    assert "请给我一个例子" in text and "不会重新发送" in text


def test_unfiled_and_completed_empty_answer_are_truthful():
    content, _ = export.conversation_document(
        record(topic_title=None, assistant_content=None, citations=[])
    )
    assert "未归入学习主题" in content.decode()
    assert "已回复" in content.decode() and "当时保存的引用" not in content.decode()


def test_all_untrusted_text_stays_inert_with_no_network_links():
    evil = '</title><script>alert(1)</script><img src="https://bad.example/a" onerror="alert(2)">'
    item = record(
        topic_title=evil,
        user_content=evil,
        assistant_content=evil
        + "\n\n[链接](https://bad.example)\n\n![图片](https://bad.example/i)",
        citations=[{"title": evil, "locator": evil, "excerpt": evil}],
    )
    content, name = export.conversation_document(item)
    html = content.decode()
    assert "&lt;script&gt;" in html
    assert all(
        tag not in {"script", "img", "a", "iframe", "form"}
        for tag, _ in Tags(html).tags
    )
    assert all(
        not key.startswith("on") for _, attrs in Tags(html).tags for key in attrs
    )
    assert "bad.example" not in name and name.endswith("-7.html")


@pytest.mark.parametrize(
    "field", ["user_content", "assistant_content", "topic_title", "citation"]
)
def test_input_budget_includes_every_exported_field(field, monkeypatch):
    monkeypatch.setattr(export, "MAX_TEXT", 100)
    item = record()
    if field == "citation":
        item["citations"][0]["excerpt"] = "字" * 101
    else:
        item[field] = "字" * 101
    with pytest.raises(ValueError):
        export.conversation_document(item)


def test_output_budget_counts_encoded_bytes(monkeypatch):
    item = record()
    content, _ = export.conversation_document(item)
    monkeypatch.setattr(export, "MAX_BYTES", len(content))
    assert export.conversation_document(item)[0] == content
    monkeypatch.setattr(export, "MAX_BYTES", len(content) - 1)
    with pytest.raises(ValueError):
        export.conversation_document(item)


def test_unknown_state_is_not_exported():
    with pytest.raises(ValueError):
        export.conversation_document(record(status="invented"))
