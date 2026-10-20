import json
import secrets
import sqlite3

import pytest
from fastapi.testclient import TestClient

from coach.materials import MaterialRepository
from tests import test_web_lesson_revision as base
from tests.test_coach_materials import pdf_bytes
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


def set_source(repo, user, identity, source):
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_knowledge SET citations_json=? WHERE user_id=? AND knowledge_id=?",
            (json.dumps([source], ensure_ascii=False), user, identity),
        )


def source_record(setup, *, identity=None):
    _, _, repo, user, saved = setup
    identity = identity or saved
    materials = MaterialRepository(repo.database_path.parent / "coach_library.db")
    raw = "甲" * 850 + "引用核心文字" + "乙" * 300 + "片段尾部独有内容" + "丙" * 1000
    book = materials.add(user.user_id, "notes.txt", raw.encode(), title="<当前资料名>")
    chunk = materials.chunks(user.user_id, book)[1]
    source = {
        "material_id": book,
        "source_id": chunk["chunk_id"],
        "title": "整理时的旧书名",
        "locator": chunk["locator"],
        "excerpt": chunk["content"][40:100],
    }
    set_source(repo, user.user_id, identity, source)
    return materials, book, chunk, source, f"/web/knowledge/{identity}/sources/1"


def test_reference_round_trip_keeps_snapshot_current_name_and_learning_unchanged(setup):
    _, client, repo, user, identity = setup
    materials, book, chunk, source, path = source_record(setup)
    other = materials.add(
        user.user_id, "other.txt", b"CURRENT_MATERIAL", title="当前讨论资料"
    )
    repo.select_material_part(
        user.user_id,
        other,
        "当前讨论资料",
        materials.chunks(user.user_id, other)[0]["chunk_id"],
    )
    current = repo.active_topic(user.user_id)
    assert (
        repo.revise_knowledge(
            user.user_id, identity, 1, title="当前第2版教案", content="后来的修订正文"
        )
        == "updated"
    )
    before = {p: p.read_bytes() for p in (repo.database_path, materials.database_path)}
    original = client.get("/web/knowledge/" + identity)
    assert (
        path in Links(original.text).links and 'id="lesson-source-1"' in original.text
    )
    found = client.get(path)
    assert found.status_code == 200
    assert "整理时的旧书名" in found.text and "&lt;当前资料名&gt;" in found.text
    assert "片段尾部独有内容" in found.text and source["excerpt"] in found.text
    assert "当前教案 · 第 2 版" in found.text
    back = f"/web/knowledge/{identity}#lesson-source-1"
    preview = f"/web/materials/{book}?part={chunk['chunk_index']}"
    assert back in Links(found.text).links and preview in Links(found.text).links
    returned = client.get(back)
    assert "后来的修订正文" in returned.text and "整理时的旧书名" in returned.text
    raw = client.get(preview)
    assert raw.status_code == 200 and "文字预览 · 片段 2" in raw.text
    assert repo.active_topic(user.user_id) == current
    assert all(p.read_bytes() == content for p, content in before.items())
    assert (
        found.headers["cache-control"] == "no-store"
        and found.headers["referrer-policy"] == "no-referrer"
    )


def test_pending_draft_reference_does_not_confirm_or_create_revision(setup):
    _, client, repo, user, _ = setup
    draft = saved_lesson(repo, user.user_id, title="待确认教案", save=False)
    _, _, _, _, path = source_record(setup, identity=draft)
    before = repo.database_path.read_bytes()
    page = client.get(path)
    assert page.status_code == 200 and "待你确认的草稿" in page.text
    assert repo.knowledge(user.user_id, draft)["status"] == "pending"
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize(
    "kind", ["legacy", "material-missing", "chunk-missing", "foreign", "wrong-book"]
)
def test_unavailable_or_wrong_owner_source_keeps_snapshot_without_guessing(setup, kind):
    _, client, repo, user, identity = setup
    materials, book, _, source, path = source_record(setup)
    private = materials.add(
        "someone-else",
        "private.txt",
        b"PRIVATE_FOREIGN_FULL_TEXT",
        title="PRIVATE_FOREIGN_TITLE",
    )
    foreign_chunk = materials.chunks("someone-else", private)[0]
    if kind == "legacy":
        source.pop("source_id")
    elif kind == "material-missing":
        source["material_id"] = "f" * 32
    elif kind == "chunk-missing":
        source["source_id"] = "e" * 32
    elif kind == "foreign":
        source.update(material_id=private, source_id=foreign_chunk["chunk_id"])
    else:
        own = materials.add(
            user.user_id, "another.txt", b"ANOTHER_OWN_BOOK_TEXT", title="另一本书"
        )
        source["source_id"] = materials.chunks(user.user_id, own)[0]["chunk_id"]
        assert source["material_id"] == book
    source["excerpt"] = "历史保存的摘录仍可读"
    set_source(repo, user.user_id, identity, source)
    before = {p: p.read_bytes() for p in (repo.database_path, materials.database_path)}
    found = client.get(path)
    assert found.status_code == 200 and "对应原文暂不可用" in found.text
    assert source["excerpt"] in found.text and "不按名称或文字" in found.text
    assert (
        "PRIVATE_FOREIGN" not in found.text
        and "ANOTHER_OWN_BOOK_TEXT" not in found.text
    )
    assert not any("?part=" in url for url in Links(found.text).links)
    assert all(p.read_bytes() == content for p, content in before.items())


def test_snapshot_that_does_not_match_current_chunk_has_explicit_mismatch_notice(setup):
    _, client, repo, user, identity = setup
    _, _, _, source, path = source_record(setup)
    source["excerpt"] = "这段文字未出现在当前片段中"
    set_source(repo, user.user_id, identity, source)
    found = client.get(path)
    assert found.status_code == 200 and "未能完全对上" in found.text
    assert source["excerpt"] in found.text and "片段尾部独有内容" in found.text


def test_book_title_snapshot_and_original_html_are_only_plain_text(setup):
    _, client, repo, user, identity = setup
    materials = MaterialRepository(repo.database_path.parent / "coach_library.db")
    raw = "<img src=x onerror=alert(1)>\n<script>只作文字</script>"
    book = materials.add(
        user.user_id, "safe.txt", raw.encode(), title="<script>书名</script>"
    )
    chunk = materials.chunks(user.user_id, book)[0]
    source = dict(
        material_id=book,
        source_id=chunk["chunk_id"],
        title="<iframe>旧名",
        locator="<img>位置",
        excerpt=raw,
    )
    set_source(repo, user.user_id, identity, source)
    response = client.get(f"/web/knowledge/{identity}/sources/1")
    assert response.status_code == 200
    assert (
        "<script>只作文字" not in response.text
        and "&lt;script&gt;只作文字" in response.text
    )
    assert "<iframe>旧名" not in response.text and "<img src=x" not in response.text
    assert "default-src 'none'" in response.headers["content-security-policy"]


@pytest.mark.parametrize("number", ["0", "-1", "01", "999", "1000"])
def test_invalid_source_numbers_are_not_used_to_read_a_different_record(setup, number):
    _, client, repo, _, identity = setup
    source_record(setup)
    before = repo.database_path.read_bytes()
    assert client.get(f"/web/knowledge/{identity}/sources/{number}").status_code == 404
    assert repo.database_path.read_bytes() == before


def test_guest_other_account_and_extra_query_cannot_read_source(setup):
    app, client, _, _, _ = setup
    _, _, _, _, path = source_record(setup)
    with TestClient(app, base_url=BASE) as stranger:
        assert stranger.get(path, follow_redirects=False).status_code == 303
        login(stranger, "two@example.com")
        response = stranger.get(path)
        assert response.status_code == 404 and "引用核心文字" not in response.text
    assert client.get(path + "?user_id=one").status_code == 400


def test_material_database_failure_keeps_snapshot_without_exposing_details(
    setup, monkeypatch
):
    _, client, _, _, _ = setup
    materials, _, _, source, path = source_record(setup)
    original = type(materials).chunk

    def broken(*a, **k):
        raise sqlite3.OperationalError("SECRET_INTERNAL_LOCATION")

    monkeypatch.setattr(type(materials), "chunk", broken)
    failed = client.get(path)
    assert failed.status_code == 503 and source["excerpt"] in failed.text
    assert (
        "SECRET_INTERNAL_LOCATION" not in failed.text
        and "原文暂时无法读取" in failed.text
    )
    monkeypatch.setattr(type(materials), "chunk", original)
    assert client.get(path).status_code == 200


def test_reading_reference_does_not_expire_pending_reply_or_change_ai_usage(setup):
    _, client, repo, user, _ = setup
    _, _, _, _, path = source_record(setup)
    nonce = secrets.token_urlsafe(32)
    assert (
        repo.claim(user.user_id, nonce, "未结束的消息", now=1, ai_kind="dialogue")
        == "claimed"
    )
    before = repo.database_path.read_bytes()
    assert client.get(path).status_code == 200
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute(
                "SELECT status FROM coach_turns WHERE nonce=?", (nonce,)
            ).fetchone()[0]
            == "pending"
        )
        assert db.execute("SELECT count(*) FROM coach_ai_usage").fetchone()[0] == 1
    assert repo.database_path.read_bytes() == before


def test_pdf_reference_uses_actual_stored_page_locator(setup):
    _, client, repo, user, identity = setup
    materials = MaterialRepository(repo.database_path.parent / "coach_library.db")
    book = materials.add(user.user_id, "reference.pdf", pdf_bytes())
    chunk = materials.chunks(user.user_id, book)[0]
    source = dict(
        material_id=book,
        source_id=chunk["chunk_id"],
        title="PDF原资料",
        locator=chunk["locator"],
        excerpt=chunk["content"],
    )
    set_source(repo, user.user_id, identity, source)
    page = client.get(f"/web/knowledge/{identity}/sources/1")
    assert page.status_code == 200 and "PDF 第 1 页" in page.text
    assert "Spaced practice improves learning." in page.text
