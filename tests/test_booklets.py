import json
import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from zipfile import ZipFile

import pytest

from api.asset_export import build_export, export_summary, ExportError, booklet_document
from coach.booklets import booklet_markdown
from conversation.coach_repository import CoachRepository
from tests import test_asset_export as base_tests

records = base_tests.records


def create(repo, title="我的学习手册", user="one", identity=None):
    identity = identity or uuid4().hex
    assert repo.create_booklet(user, identity, title) == "saved"
    return identity


def change(repo, identity, operation, *, lesson=None, title=None, revision=None):
    revision = revision or repo.booklet("one", identity, chapter=0)["revision"]
    return repo.change_booklet(
        "one", identity, revision, operation, knowledge_id=lesson, title=title
    )


def lesson(repo, title="补充教案", user="one"):
    nonce = secrets.token_urlsafe(32)
    repo.claim(user, nonce, "整理", now=base_tests.NOW)
    repo.finish(
        user,
        nonce,
        "草稿",
        None,
        now=base_tests.NOW,
        draft={"title": title, "topic": "主题", "content": "可重温的正文。"},
    )
    identity = repo.list_knowledge(user, status="pending")[0]["knowledge_id"]
    repo.confirm_knowledge(user, identity)
    return identity


def test_only_saved_owned_lessons_can_be_collected_and_remove_is_reversible(records):
    repo, _, _ = records
    saved = repo.list_knowledge("one")[0]["knowledge_id"]
    draft = repo.list_knowledge("one", status="pending")[0]["knowledge_id"]
    foreign = repo.list_knowledge("two", status="pending")[0]["knowledge_id"]
    book = create(repo)
    before = repo.view("one", now=base_tests.NOW)
    for invalid in (draft, foreign, uuid4().hex):
        with pytest.raises(ValueError, match="确认保存"):
            change(repo, book, "add", lesson=invalid)
    assert change(repo, book, "add", lesson=saved) == "saved"
    assert change(repo, book, "add", lesson=saved) == "unchanged"
    assert len(repo.booklet("one", book)["chapters"]) == 1
    assert change(repo, book, "remove", lesson=saved) == "saved"
    assert repo.booklet("one", book)["chapters"] == []
    assert repo.knowledge("one", saved, saved_only=True)
    assert change(repo, book, "add", lesson=saved) == "saved"
    assert repo.view("one", now=base_tests.NOW) == before
    assert repo.booklet("two", book) is None and repo.list_booklets("two") == []


def test_order_latest_revision_and_restart_without_copying_content(records):
    repo, _, _ = records
    a = repo.list_knowledge("one")[0]["knowledge_id"]
    b = lesson(repo, "第二章")
    book = create(repo)
    for identity in (a, b):
        change(repo, book, "add", lesson=identity)
    assert change(repo, book, "down", lesson=a) == "saved"
    snapshot = repo.booklet("one", book)
    assert [item["knowledge_id"] for item in snapshot["chapters"]] == [b, a]
    assert change(repo, book, "up", lesson=b) == "unchanged"
    assert (
        repo.revise_knowledge("one", a, 1, title="修订后的章节", content="最新版正文。")
        == "updated"
    )
    current = CoachRepository(repo.database_path).booklet("one", book, chapter=2)
    assert (
        current["chapters"][1]["revision"] == 2
        and current["chapters"][1]["content"] == "最新版正文。"
    )
    assert current["chapters"][0]["content"] is None
    assert snapshot["chapters"][1]["content"] != current["chapters"][1]["content"]
    with sqlite3.connect(repo.database_path) as db:
        stored = db.execute(
            "SELECT lesson_ids_json FROM coach_booklets WHERE booklet_id=?", (book,)
        ).fetchone()[0]
    assert json.loads(stored) == [b, a] and "最新版正文" not in stored


def test_concurrent_edits_and_stale_membership_are_not_overwritten(records):
    repo, _, _ = records
    book = create(repo)

    def rename(index):
        return repo.change_booklet("one", book, 1, "title", title="名称" + str(index))

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(rename, range(2))) == ["conflict", "saved"]
    saved = repo.list_knowledge("one")[0]["knowledge_id"]
    assert change(repo, book, "add", lesson=saved, revision=1) == "conflict"
    assert repo.booklet("one", book)["chapters"] == []
    assert repo.change_booklet("other", book, 2, "title", title="不应覆盖") == "missing"


def test_create_is_idempotent_and_rollback_preserves_directory(records):
    repo, _, _ = records
    book = create(repo)
    assert repo.create_booklet("one", book, "不应再次创建") == "unchanged"
    assert repo.create_booklet("other", book, "不应覆盖") == "missing"
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "CREATE TRIGGER fail_booklet BEFORE UPDATE ON coach_booklets BEGIN SELECT RAISE(ABORT,'test'); END"
        )
    before = repo.booklet("one", book)
    with pytest.raises(sqlite3.Error):
        change(repo, book, "title", title="失败的名称")
    assert repo.booklet("one", book) == before


def test_corrupt_foreign_chapter_never_leaks_and_can_be_removed(records):
    repo, _, _ = records
    other = lesson(repo, "OTHER-SECRET", user="two")
    book = create(repo)
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "UPDATE coach_booklets SET lesson_ids_json=? WHERE booklet_id=?",
            (json.dumps([other]), book),
        )
    snapshot = repo.booklet("one", book)
    assert snapshot["chapters"][0]["missing"] and "OTHER-SECRET" not in str(snapshot)
    assert "OTHER-SECRET" not in booklet_document(snapshot)
    assert change(repo, book, "remove", lesson=other) == "saved"
    assert repo.knowledge("two", other, saved_only=True)


def test_booklet_export_only_own_latest_content_and_safe_offline_html(records):
    repo, materials, _ = records
    book = create(repo, "../../CON:<手册>")
    saved = repo.list_knowledge("one")[0]["knowledge_id"]
    change(repo, book, "add", lesson=saved)
    create(repo, "OTHER-PRIVATE-BOOK", user="two")
    assert (
        export_summary(repo.database_path, materials.database_path, "one")["booklets"]
        == 1
    )
    bundle = build_export(
        repo.database_path,
        materials.database_path,
        "one",
        ["booklets"],
        period="30",
        now=base_tests.NOW + 99999999,
    )
    try:
        with ZipFile(bundle.file) as archive:
            names = archive.namelist()
            html = archive.read(
                next(
                    name
                    for name in names
                    if name.startswith("学习手册/") and name.endswith(".html")
                )
            ).decode()
            md = archive.read(
                next(
                    name
                    for name in names
                    if name.startswith("学习手册/") and name.endswith(".md")
                )
            ).decode()
            assert base_tests.Links(html).active == []
            assert "&lt;手册&gt;" in html and "教案版本：第 1 版" in md
            assert (
                "real-fragment" not in html
            )  # Opaque ids stay out of reading documents.
            assert "任务边界原文" in html and "OTHER-PRIVATE" not in html + md
            assert all(".." not in name.split("/") for name in names)
    finally:
        bundle.close()


def test_export_old_database_without_booklets_does_not_migrate(records):
    repo, materials, _ = records
    with sqlite3.connect(repo.database_path) as db:
        db.execute("DROP TABLE coach_booklets")
    assert (
        export_summary(repo.database_path, materials.database_path, "one")["booklets"]
        == 0
    )
    bundle = build_export(repo.database_path, materials.database_path, "one", ["saved"])
    bundle.close()
    with pytest.raises(ExportError):
        build_export(repo.database_path, materials.database_path, "one", ["booklets"])
    with sqlite3.connect(repo.database_path) as db:
        assert (
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='coach_booklets'"
            ).fetchone()
            is None
        )


@pytest.mark.parametrize("title", ["", "  ", "字" * 121, "含\n换行", "含\x00字符"])
def test_invalid_names_do_not_create_booklets(records, title):
    repo, _, _ = records
    with pytest.raises(ValueError):
        create(repo, title)
    assert repo.list_booklets("one") == []


def test_booklet_count_limit_is_enforced_inside_transaction(records):
    repo, _, _ = records
    for index in range(50):
        create(repo, str(index))
    with pytest.raises(ValueError, match="50"):
        create(repo, "超过上限")
    assert len(repo.list_booklets("one", limit=100)) == 50


def test_chapter_limit_and_empty_booklet_export(records):
    repo, _, _ = records
    book = create(repo)
    assert "尚未收录" in booklet_markdown(repo.booklet("one", book))
    ids = [uuid4().hex for _ in range(101)]
    with sqlite3.connect(repo.database_path) as db:
        db.executemany(
            "INSERT INTO coach_knowledge VALUES(?,'one',?,'章节','主题','正文','[]','saved',1000,1000)",
            [(identity, 10000 + index) for index, identity in enumerate(ids)],
        )
        db.execute(
            "UPDATE coach_booklets SET lesson_ids_json=? WHERE booklet_id=?",
            (json.dumps(ids[:100]), book),
        )
    with pytest.raises(ValueError, match="100"):
        change(repo, book, "add", lesson=ids[-1])
    assert len(repo.booklet("one", book)["chapters"]) == 100
