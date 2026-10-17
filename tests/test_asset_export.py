import hashlib
import io
import secrets
import posixpath
from pathlib import PurePosixPath
from urllib.parse import unquote
from html.parser import HTMLParser
from zipfile import ZipFile

import pytest

from api import asset_export
from api.asset_export import build_export, export_summary, ExportError
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository


NOW = 1792200000
RICH = "## 核心知识\n\n**理解任务边界**\n\n| 项目 | 内容 |\n| --- | --- |\n| 学习 | 每天一点 |\n\n```python\ndef learn():\n    return 1\n```\n\n<script>不能执行</script>\n![x](https://outside.example/x)"


class Links(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.links = []
        self.active = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a":
            self.links.append(attrs.get("href", ""))
        if tag in {"script", "img", "iframe", "object", "form"}:
            self.active.append(tag)


@pytest.fixture
def records(tmp_path):
    coach = CoachRepository(tmp_path / "coach_conversations.db")
    materials = MaterialRepository(tmp_path / "coach_library.db")
    nonce = secrets.token_urlsafe(32)
    source = {
        "source_id": "real-fragment",
        "material_id": "book",
        "title": "<资料标题>",
        "locator": "片段 1",
        "excerpt": "<img src=x onerror=alert(1)>任务边界原文",
    }
    coach.claim("one", nonce, "<b>我的问题</b>", now=NOW - 10)
    coach.finish(
        "one",
        nonce,
        RICH,
        {"topic": "任务边界", "progress": "已讨论边界", "next_step": "举一个例子"},
        now=NOW - 9,
        citations=[source],
        draft={"title": "../../CON:<草稿>", "topic": "任务边界", "content": RICH},
    )
    saved = coach.list_knowledge("one", status="pending")[0]["knowledge_id"]
    coach.confirm_knowledge("one", saved)
    nonce2 = secrets.token_urlsafe(32)
    coach.claim("one", nonce2, "请整理教案", now=NOW - 8)
    coach.finish(
        "one",
        nonce2,
        "待确认",
        None,
        now=NOW - 7,
        draft={"title": "待确认内容", "topic": "复习", "content": RICH},
    )
    material = materials.add(
        "one",
        "../../CON?.md",
        b"\xef\xbb\xbf# original\r\nkeep bytes",
        title="我的原始资料",
    )
    materials.select("one", material)
    other_nonce = secrets.token_urlsafe(32)
    coach.claim("two", other_nonce, "other-private-question", now=NOW)
    coach.finish(
        "two",
        other_nonce,
        "other-private-answer",
        None,
        now=NOW,
        draft={
            "title": "other-private-title",
            "topic": "other-private-topic",
            "content": "other-private-lesson",
        },
    )
    materials.add(
        "two", "private.txt", b"other-private-material", title="other-private-file"
    )
    return coach, materials, nonce


def contents(archive):
    with ZipFile(io.BytesIO(b"".join(archive.chunks()))) as zipped:
        return {name: zipped.read(name) for name in zipped.namelist()}


def test_full_export_is_readable_owned_safe_and_does_not_change_sources(records):
    coach, materials, nonce = records
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (coach.database_path, materials.database_path)
    }
    archive = build_export(
        coach.database_path,
        materials.database_path,
        "one",
        ["saved", "drafts", "chat", "materials"],
        now=NOW,
    )
    assert archive.size > 0 and archive.filename.endswith(".zip")
    files = contents(archive)
    assert archive.file.closed
    assert "打开这里.html" in files and "使用说明.txt" in files
    assert sum(name.endswith(".md") and name.startswith("教案/") for name in files) == 2
    payload = b"\n".join(files.values())
    for private in [
        b"other-private-",
        nonce.encode(),
        b"$argon2id$",
        b"coach_login_session",
    ]:
        assert private not in payload
    for name in files:
        assert (
            not name.startswith(("/", "\\"))
            and ".." not in PurePosixPath(name).parts
            and "\\" not in name
        )
        if name.endswith(".html"):
            parser = Links(files[name].decode())
            assert parser.active == []
            assert not any(
                link.startswith(("http:", "https:", "javascript:", "//"))
                for link in parser.links
            )
            for link in parser.links:
                resolved = posixpath.normpath(
                    str(PurePosixPath(name).parent / unquote(link))
                )
                assert resolved in files
    index = files["打开这里.html"].decode()
    for link in Links(index).links:
        assert unquote(link) in files
    saved_html = next(
        value.decode()
        for name, value in files.items()
        if name.startswith("教案/已保存/") and name.endswith(".html")
    )
    assert "<h2>核心知识</h2>" in saved_html and "<table>" in saved_html
    assert "def learn():\n    return 1" in saved_html
    assert "引用依据" in saved_html and "&lt;img" in saved_html
    draft_html = next(
        value.decode()
        for name, value in files.items()
        if name.startswith("教案/待确认草稿/") and name.endswith(".html")
    )
    assert "待确认草稿，尚未保存到知识库" in draft_html
    original = next(
        value for name, value in files.items() if name.startswith("原始资料/")
    )
    assert original == b"\xef\xbb\xbf# original\r\nkeep bytes"
    assert (
        export_summary(coach.database_path, materials.database_path, "one")["saved"]
        == 1
    )
    assert len(coach.list_knowledge("one", status="pending")) == 1
    assert materials.selected("one") is not None
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == digest
        for p, digest in before.items()
    )


def test_selected_scope_does_not_silently_include_other_assets(records):
    coach, materials, _ = records
    files = contents(
        build_export(
            coach.database_path, materials.database_path, "one", ["saved"], now=NOW
        )
    )
    assert all(
        not name.startswith(("原始资料/", "对话/", "教案/待确认草稿/"))
        for name in files
    )


def test_chat_period_filters_messages_but_keeps_current_learning_position(records):
    coach, materials, _ = records
    nonce = secrets.token_urlsafe(32)
    coach.claim("one", nonce, "very-old-question", now=NOW - 100 * 86400)
    coach.finish("one", nonce, "very-old-answer", None, now=NOW - 100 * 86400)
    files = contents(
        build_export(
            coach.database_path,
            materials.database_path,
            "one",
            ["chat"],
            period="30",
            now=NOW,
        )
    )
    assert b"very-old-question" not in b"\n".join(files.values())
    assert "对话/当前学习位置.txt" in files
    assert "<b>我的问题</b>" not in files["对话/记录/聊天记录.html"].decode()
    assert "&lt;b&gt;我的问题&lt;/b&gt;" in files["对话/记录/聊天记录.html"].decode()


@pytest.mark.parametrize(
    "scopes,period",
    [
        ([], "all"),
        (["unknown"], "all"),
        (["saved", "saved"], "all"),
        (["saved"], "yesterday"),
    ],
)
def test_invalid_selection_is_rejected(records, scopes, period):
    coach, materials, _ = records
    with pytest.raises(ExportError):
        build_export(
            coach.database_path, materials.database_path, "one", scopes, period=period
        )


def test_empty_selection_range_has_clear_error(records):
    coach, materials, _ = records
    with pytest.raises(ExportError, match="没有可导出"):
        build_export(
            coach.database_path,
            materials.database_path,
            "empty-user",
            ["saved"],
            now=NOW,
        )


def test_size_limit_closes_temporary_file_and_keeps_records(records, monkeypatch):
    coach, materials, _ = records
    created = []
    factory = asset_export.SpooledTemporaryFile

    def tracked(*args, **kwargs):
        result = factory(*args, **kwargs)
        created.append(result)
        return result

    monkeypatch.setattr(asset_export, "SpooledTemporaryFile", tracked)
    monkeypatch.setattr(asset_export, "MAX_BYTES", 100)
    with pytest.raises(ExportError, match="上限"):
        build_export(
            coach.database_path, materials.database_path, "one", ["saved"], now=NOW
        )
    assert created and all(file.closed for file in created)
    assert coach.list_knowledge("one")


def test_closing_download_iterator_releases_temporary_archive(records):
    coach, materials, _ = records
    archive = build_export(
        coach.database_path, materials.database_path, "one", ["saved"], now=NOW
    )
    iterator = archive.chunks()
    assert next(iterator)
    iterator.close()
    assert archive.file.closed


def test_current_learning_can_export_without_chat_turns(records):
    coach, materials, _ = records
    with coach._connect() as db:
        db.execute(
            "INSERT INTO coach_learning VALUES('new','主题','进度','下一步',?)", (NOW,)
        )
    files = contents(
        build_export(
            coach.database_path, materials.database_path, "new", ["chat"], now=NOW
        )
    )
    assert "对话/当前学习位置.txt" in files
