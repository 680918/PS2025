import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from zipfile import ZipFile

import pytest

from api.asset_export import build_export, export_summary
from coach.book_study import study_directory, unit_chunks
from coach.dialogue import CoachAnswer
from coach.learning_topics import TopicBusy
from conversation.coach_repository import CoachRepository
from tests import test_book_section as base_tests

setup = base_tests.setup
select = base_tests.select
send = base_tests.send


def save_unit(
    repo, book, start=1, end=2, *, identity=None, revision=0, title="第一单元"
):
    identity = identity or uuid4().hex
    result = repo.save_book_unit(
        "one", book, identity, title, start, end, revision, now=1000
    )
    return identity, result


def explained(history, message, learning, *, context):
    return CoachAnswer(
        "本段讲解。", used_source_ids=[row["source_id"] for row in context["sources"]]
    )


def state(repo, materials, book):
    stored = repo.book_position("one", book)
    return study_directory(
        materials.get("one", book),
        materials.chunks("one", book),
        repo.book_units("one", book),
        repo.book_coverage("one", book),
        stored["chunk_id"] if stored else None,
    )


def test_coverage_only_for_successful_explicit_cited_study_and_never_mastery(setup):
    repo, materials, a, _ = setup
    select(repo, materials, a, 1)
    assert (
        send(repo, materials, action="message", text="讲解这段", responder=explained)
        == "complete"
    )
    assert repo.book_coverage("one", a) == []
    assert (
        send(repo, materials, responder=lambda *a, **k: CoachAnswer("无法据此讲解"))
        == "complete"
    )
    assert repo.book_coverage("one", a) == []
    nonce = secrets.token_urlsafe(32)
    assert send(repo, materials, responder=explained, nonce=nonce) == "complete"
    assert send(repo, materials, responder=explained, nonce=nonce) == "duplicate"
    assert len(repo.book_coverage("one", a)) == 1
    assert state(repo, materials, a)["explained"] == 1
    assert state(repo, materials, a)["next"]["chunk_index"] == 2
    assert repo.book_coverage("other", a) == []


def test_failure_expiration_and_rollback_cannot_increase_coverage(setup):
    repo, materials, a, _ = setup
    _, part = select(repo, materials, a, 1)
    assert send(repo, materials, responder=lambda *a, **k: CoachAnswer("")) == "failed"
    assert repo.book_coverage("one", a) == []
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "test", now=1002)
    assert not repo.finish(
        "one",
        nonce,
        "late",
        None,
        now=1200,
        material_id=a,
        part_id=part["chunk_id"],
        explained_part=True,
    )
    assert repo.book_coverage("one", a) == []
    repo.view("one", now=1200)
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "CREATE TRIGGER coverage_fail BEFORE INSERT ON coach_book_coverage BEGIN SELECT RAISE(ABORT,'test'); END"
        )
    assert send(repo, materials, responder=explained, now=1201) == "failed"
    assert repo.book_coverage("one", a) == []
    assert repo.view("one", now=1202)["turns"][-1]["status"] == "failed"


def test_unit_bounds_progress_and_next_respect_unit_end_and_restart(setup):
    repo, materials, a, b = setup
    unit, _ = save_unit(repo, a, 1, 2)
    _, part = select(repo, materials, a, 2)
    assert send(repo, materials, responder=explained) == "complete"
    current = state(repo, materials, a)
    assert current["unit"]["unit_id"] == unit
    assert current["unit"]["explained"] == 1 and current["unit"]["total"] == 2
    assert current["next"] is None
    select(repo, materials, b, 1, now=1002)
    restored = CoachRepository(repo.database_path, materials=materials)
    assert restored.book_position("one", a)["chunk_id"] == part["chunk_id"]
    assert state(restored, materials, a)["explained"] == 1
    assert state(restored, materials, b)["explained"] == 0
    assert save_unit(repo, a, 2, 3, identity=unit, revision=1)[1] == "saved"
    changed = state(repo, materials, a)
    assert changed["unit"]["explained"] == 1
    assert changed["next"]["chunk_index"] == 3
    assert len(repo.book_coverage("one", a)) == 1


def test_edit_conflict_overlap_and_owner_never_overwrite_other_changes(setup):
    repo, _, a, b = setup
    unit, _ = save_unit(repo, a)
    assert save_unit(repo, a, identity=unit, revision=1)[1] == "unchanged"
    assert save_unit(repo, a, identity=unit, revision=1, title="新标题")[1] == "saved"
    assert (
        save_unit(repo, a, identity=unit, revision=1, title="过期修改")[1] == "conflict"
    )
    assert repo.book_units("one", a)[0]["title"] == "新标题"
    assert repo.book_units("other", a) == []
    assert (
        repo.save_book_unit("other", a, unit, "不应覆盖", 1, 2, 0, now=1000)
        == "missing"
    )
    assert save_unit(repo, b, identity=unit, revision=1)[1] == "missing"
    with pytest.raises(ValueError, match="重叠"):
        save_unit(repo, a, 2, 3)
    assert len(repo.book_units("one", a)) == 1


def test_concurrent_overlapping_units_are_serialized_and_busy_blocks_edits(setup):
    repo, _, a, _ = setup

    def attempt(_):
        try:
            return save_unit(repo, a)[1]
        except ValueError:
            return "overlap"

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(attempt, range(2))) == ["overlap", "saved"]
    repo.claim("one", secrets.token_urlsafe(32), "pending", now=1000)
    with pytest.raises(TopicBusy):
        save_unit(repo, a, 3, 3)
    assert len(repo.book_units("one", a)) == 1


def test_pdf_ranges_use_file_pages_including_blank_pages_not_chunk_numbers():
    item = {"kind": "pdf", "page_count": 4}
    chunks = [
        {"chunk_id": "a", "chunk_index": 1, "locator": "PDF 第 1 页 · 片段 1"},
        {"chunk_id": "b", "chunk_index": 2, "locator": "PDF 第 3 页 · 片段 2"},
        {"chunk_id": "c", "chunk_index": 3, "locator": "PDF 第 3 页 · 片段 3"},
    ]
    assert unit_chunks(item, chunks, 2, 2) == []
    assert [row["chunk_id"] for row in unit_chunks(item, chunks, 2, 3)] == ["b", "c"]
    for start, end in [(0, 1), (3, 2), (1, 5), (True, 2), ("1", 2)]:
        with pytest.raises(ValueError):
            unit_chunks(item, chunks, start, end)


def test_directory_export_is_private_and_not_limited_by_chat_period(setup):
    repo, materials, a, _ = setup
    save_unit(repo, a, title="私有读书单元")
    repo.save_book_unit("other", a, uuid4().hex, "OTHER-SECRET", 1, 2, 0, now=1000)
    assert export_summary(repo.database_path, materials.database_path, "one")[
        "learning"
    ]
    bundle = build_export(
        repo.database_path,
        materials.database_path,
        "one",
        ["chat"],
        period="30",
        now=99999999,
    )
    try:
        with ZipFile(bundle.file) as archive:
            text = archive.read("书籍学习/学习目录.txt").decode()
            assert "私有读书单元" in text and "OTHER-SECRET" not in text
            assert "0 / 3" in text and "片段 3 · 待讲解" in text
            assert "书籍学习/学习目录.html" in archive.namelist()
    finally:
        bundle.close()
