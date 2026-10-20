import json
import sqlite3
from uuid import uuid4

import pytest

from conversation.coach_repository import CoachRepository
from tests.test_lesson_revision import saved_lesson


def make_book(repo, user, ids, title="学习手册"):
    book = uuid4().hex
    repo.create_booklet(user, book, title)
    for revision, identity in enumerate(ids, 1):
        assert (
            repo.change_booklet(user, book, revision, "add", knowledge_id=identity)
            == "saved"
        )
    return book


@pytest.fixture
def repo(tmp_path):
    return CoachRepository(tmp_path / "dialogue.db")


def test_scoped_current_fields_literal_matching_and_read_only_restart(repo):
    first = saved_lesson(
        repo,
        title="Title KEY",
        content="起点 " + "前文" * 100 + " Needle 100%_ " + "后文" * 100,
    )
    second = saved_lesson(repo, title="另一章", content="不匹配")
    saved_lesson(repo, title="未收录 Needle", content="Needle")
    book = make_book(repo, "one", [second, first])
    before = repo.database_path.read_bytes()
    found = repo.find_booklet("one", book, "nEeDlE")
    assert found["total"] == 1 and found["items"][0]["number"] == 2
    item = found["items"][0]
    assert item["knowledge_id"] == first and item["search_match"]["fields"] == ["正文"]
    assert len(item["search_match"]["excerpt"]["text"]) <= 146
    assert all(key not in item for key in ("content", "citations", "user_id", "nonce"))
    assert repo.find_booklet("one", book, "KEY")["items"][0]["search_match"][
        "fields"
    ] == ["标题"]
    assert repo.find_booklet("one", book, "学习方法")["total"] == 2
    assert repo.find_booklet("one", book, "100%_")["total"] == 1
    assert repo.find_booklet("one", book, "原始依据")["total"] == 0
    assert repo.find_booklet("one", book, "")["items"] == []
    assert repo.database_path.read_bytes() == before
    assert (
        CoachRepository(repo.database_path).find_booklet("one", book, "nEeDlE") == found
    )


def test_pagination_order_and_out_of_range_are_bounded(repo):
    ids = [
        saved_lesson(repo, title=f"章节{n}", content="共同关键词") for n in range(22)
    ]
    book = make_book(repo, "one", ids)
    first = repo.find_booklet("one", book, "关键词")
    second = repo.find_booklet("one", book, "关键词", page=2)
    assert first["total"] == second["total"] == 22
    assert [x["knowledge_id"] for x in first["items"]] == ids[:20]
    assert [x["number"] for x in second["items"]] == [21, 22]
    assert repo.find_booklet("one", book, "关键词", page=10000)["items"] == []


def test_latest_revision_reorder_and_stable_lesson_open_do_not_change_position(repo):
    a = saved_lesson(repo, title="第一章", content="旧关键词")
    b = saved_lesson(repo, title="第二章", content="另一个内容")
    book = make_book(repo, "one", [a, b])
    repo.remember_booklet_position("one", book, 3, b, 0)
    repo.revise_knowledge("one", a, 1, title="修改后", content="新关键词")
    assert repo.find_booklet("one", book, "旧关键词")["total"] == 0
    hit = repo.find_booklet("one", book, "新关键词")["items"][0]
    assert hit["revision"] == 2
    repo.change_booklet("one", book, 3, "down", knowledge_id=a)
    before = repo.database_path.read_bytes()
    opened = repo.booklet("one", book, chapter=a)
    assert (
        opened["selected_chapter"] == 2
        and opened["chapters"][1]["content"] == "新关键词"
    )
    assert opened["chapters"][0]["content"] is None
    assert opened["reading_position"]["knowledge_id"] == b
    assert repo.database_path.read_bytes() == before
    repo.change_booklet("one", book, 4, "remove", knowledge_id=a)
    with pytest.raises(LookupError):
        repo.booklet("one", book, chapter=a)


def test_foreign_draft_dismissed_missing_and_uncollected_records_are_excluded(repo):
    own = saved_lesson(repo, content="共同暗号")
    draft = saved_lesson(repo, content="共同暗号", save=False)
    foreign = saved_lesson(repo, "two", content="共同暗号")
    book = make_book(repo, "one", [own])
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "UPDATE coach_booklets SET lesson_ids_json=? WHERE booklet_id=?",
            (json.dumps([own, draft, foreign, uuid4().hex]), book),
        )
    assert repo.find_booklet("two", book, "共同暗号") is None
    assert repo.find_booklet("one", uuid4().hex, "共同暗号") is None
    assert repo.find_booklet("one", book, "共同暗号")["total"] == 1
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "UPDATE coach_knowledge SET status='dismissed' WHERE knowledge_id=?", (own,)
        )
    assert repo.find_booklet("one", book, "共同暗号")["total"] == 0


@pytest.mark.parametrize(
    "query,page",
    [("x" * 121, 1), ("x\ny", 1), ("\0", 1), ("q", 0), ("q", True), ("q", 10001)],
)
def test_invalid_search_values_are_rejected(repo, query, page):
    book = make_book(repo, "one", [])
    with pytest.raises(ValueError):
        repo.find_booklet("one", book, query, page=page)
