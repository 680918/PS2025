import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from zipfile import ZipFile

import pytest

from coach.dialogue import CoachAnswer, send_dialogue
from coach.learning_topics import (
    discussion_material,
    select_discussion_material,
    TopicBusy,
)
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from api.asset_export import build_export


@pytest.fixture
def setup(tmp_path):
    materials = MaterialRepository(tmp_path / "materials.db")
    repo = CoachRepository(tmp_path / "coach.db", materials=materials)
    return repo, materials


def send(
    repo,
    text,
    *,
    user="one",
    responder=None,
    now=1000,
    study_id=None,
    materials=None,
    action="message",
    nonce=None,
):
    return send_dialogue(
        repo,
        user,
        text,
        nonce or secrets.token_urlsafe(32),
        responder=responder or (lambda *a, **k: CoachAnswer("好。")),
        now=now,
        study_id=study_id,
        materials=materials,
        action=action,
    )


def test_two_topics_resume_with_independent_progress_material_and_history(setup):
    repo, materials = setup
    book_a = materials.add("one", "python.txt", "变量用来存放数值".encode())
    book_b = materials.add("one", "reading.txt", "阅读时先提出问题".encode())
    repo.create_topic("one", "Python 入门", book_a, now=100)
    topic_a = repo.active_topic("one")["topic_id"]

    def answer_a(*args, **kwargs):
        return CoachAnswer(
            "A 的回答",
            {"topic": "Python 入门", "progress": "已讨论变量", "next_step": "尝试循环"},
        )

    send(repo, "A 独有的问题", responder=answer_a, materials=materials, now=101)
    repo.create_topic("one", "阅读方法", book_b, now=102)
    topic_b = repo.active_topic("one")["topic_id"]
    send(
        repo,
        "B 独有的问题",
        responder=lambda *a, **k: CoachAnswer(
            "B 的回答",
            {
                "topic": "阅读方法",
                "progress": "已讨论提问",
                "next_step": "比较两段材料",
            },
        ),
        materials=materials,
        now=103,
    )
    observed = []

    def resume(history, message, learning, *, context):
        observed.append((history, message, learning, context))
        return CoachAnswer(
            "回到循环。",
            {
                "topic": "模型误改名称",
                "progress": "开始讨论循环",
                "next_step": "写一个例子",
            },
        )

    nonce = secrets.token_urlsafe(32)
    assert (
        send(
            repo,
            "",
            responder=resume,
            action="continue",
            study_id=topic_a,
            materials=materials,
            now=104,
            nonce=nonce,
        )
        == "complete"
    )
    history, message, learning, context = observed[0]
    assert [m["content"] for m in history] == ["A 独有的问题", "A 的回答"]
    assert (
        message == "继续上次学习：Python 入门" and learning["progress"] == "已讨论变量"
    )
    assert context["material"]["material_id"] == book_a
    assert (
        repo.active_topic("one")["topic_id"] == topic_a
        and repo.active_topic("one")["title"] == "Python 入门"
    )
    assert repo.topic("one", topic_b)["progress"] == "已讨论提问"
    assert (
        send(
            repo,
            "",
            responder=resume,
            action="continue",
            study_id=topic_a,
            materials=materials,
            now=105,
            nonce=nonce,
        )
        == "duplicate"
    )
    assert len(observed) == 1
    assert len(repo.view("one", now=106)["turns"]) == 3


def test_material_clear_is_per_topic_and_does_not_fall_back_to_another_book(setup):
    repo, materials = setup
    book = materials.add("one", "book.txt", b"own material")
    materials.select("one", book)
    repo.create_topic("one", "主题A", book)
    a = repo.active_topic("one")["topic_id"]
    repo.create_topic("one", "主题B", "")
    assert discussion_material(repo, materials, "one") is None
    repo.activate_topic("one", a)
    assert discussion_material(repo, materials, "one")["material_id"] == book
    select_discussion_material(repo, materials, "one", None)
    assert discussion_material(repo, materials, "one") is None
    assert materials.selected("one")["material_id"] == book
    assert repo.active_topic("one")["material_id"] == ""
    with pytest.raises(ValueError):
        select_discussion_material(repo, materials, "two", book)


def test_automatic_new_topic_preserves_the_old_position_and_detour_does_not_switch(
    setup,
):
    repo, materials = setup
    send(
        repo,
        "学习A",
        responder=lambda *a, **k: CoachAnswer(
            "A", {"topic": "主题A", "progress": "A进度", "next_step": "A下一步"}
        ),
        materials=materials,
    )
    a = repo.active_topic("one")["topic_id"]
    send(repo, "临时聊个别的", materials=materials, now=1001)
    assert repo.active_topic("one")["topic_id"] == a
    send(
        repo,
        "学习B",
        responder=lambda *a, **k: CoachAnswer(
            "B", {"topic": "主题B", "progress": "B进度", "next_step": "B下一步"}
        ),
        materials=materials,
        now=1002,
    )
    assert repo.topic("one", a)["progress"] == "A进度"
    repo.activate_topic("one", a, now=1003)
    assert repo.view("one", now=1004)["learning"]["next_step"] == "A下一步"


def test_busy_provider_blocks_theme_material_and_review_switches_and_late_reply_cannot_overwrite(
    setup,
):
    repo, materials = setup
    repo.create_topic("one", "主题A", now=1000)
    a = repo.active_topic("one")["topic_id"]
    repo.create_topic("one", "主题B", now=1001)
    b = repo.active_topic("one")["topic_id"]
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "正在提问", now=1002)
    with pytest.raises(TopicBusy):
        repo.activate_topic("one", a, now=1003)
    with pytest.raises(TopicBusy):
        repo.create_topic("one", "第三主题", now=1003)
    # Use the same injected clock for mutation paths that normally use wall time.
    import conversation.coach_repository as module

    original = module.time
    try:
        module.time = lambda: 1003
        with pytest.raises(TopicBusy):
            select_discussion_material(repo, materials, "one", None)
        with pytest.raises(TopicBusy):
            repo.select_review("one", None)
    finally:
        module.time = original
    assert repo.active_topic("one")["topic_id"] == b
    repo.activate_topic("one", a, now=1183)
    assert not repo.finish(
        "one",
        nonce,
        "迟到",
        {"topic": "错误主题", "progress": "错误", "next_step": "错误"},
        now=1184,
    )
    assert repo.active_topic("one")["topic_id"] == a
    assert len(repo.list_topics("one")) == 2


def test_legacy_position_and_selected_material_migrate_once_without_guessing_chat_topics(
    tmp_path,
):
    materials = MaterialRepository(tmp_path / "materials.db")
    book = materials.add("one", "old.txt", b"old notes")
    materials.select("one", book)
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as db:
        db.execute(
            "CREATE TABLE coach_learning(user_id TEXT PRIMARY KEY,topic TEXT,progress TEXT,next_step TEXT,updated_at INTEGER)"
        )
        db.execute(
            "INSERT INTO coach_learning VALUES('one','以前的主题','保留进度','保留下一步',123)"
        )
    repo = CoachRepository(path, materials=materials)
    current = repo.active_topic("one")
    assert current["progress"] == "保留进度" and current["material_id"] == book
    restarted = CoachRepository(path, materials=materials)
    assert restarted.active_topic("one")["topic_id"] == current["topic_id"]
    assert len(restarted.list_topics("one")) == 1
    assert restarted.view("one", now=124)["learning"]["updated_at"] == 123


def test_normalized_duplicates_concurrency_and_account_ownership(setup):
    repo, _ = setup
    with ThreadPoolExecutor(2) as pool:
        results = list(
            pool.map(
                lambda title: repo.create_topic("one", title),
                ["Python 入门", "Ｐｙｔｈｏｎ 入门"],
            )
        )
    assert sorted(results) == ["created", "existing"]
    note = repo.active_topic("one")
    assert repo.topic("two", note["topic_id"]) is None
    with pytest.raises(ValueError):
        repo.activate_topic("two", note["topic_id"])
    with pytest.raises(ValueError):
        send(repo, "", user="two", action="continue", study_id=note["topic_id"])
    assert repo.list_topics("two") == []


def test_replayed_continue_nonce_cannot_switch_a_different_current_topic(setup):
    repo, materials = setup
    repo.create_topic("one", "主题A")
    a = repo.active_topic("one")["topic_id"]
    nonce = secrets.token_urlsafe(32)
    assert (
        send(repo, "", action="continue", study_id=a, nonce=nonce, materials=materials)
        == "complete"
    )
    repo.create_topic("one", "主题B")
    b = repo.active_topic("one")["topic_id"]
    assert (
        send(
            repo,
            "",
            action="continue",
            study_id=a,
            nonce=nonce,
            materials=materials,
            now=1001,
        )
        == "duplicate"
    )
    assert repo.active_topic("one")["topic_id"] == b


def test_topic_progress_and_turn_reply_roll_back_together(setup):
    repo, _ = setup
    repo.create_topic("one", "主题A")
    nonce = secrets.token_urlsafe(32)
    repo.claim("one", nonce, "提问", now=1000)
    with sqlite3.connect(repo.database_path) as db:
        db.execute(
            "CREATE TRIGGER fail_topic BEFORE UPDATE ON coach_topics BEGIN SELECT RAISE(ABORT,'test failure'); END"
        )
    with pytest.raises(sqlite3.Error):
        repo.finish(
            "one",
            nonce,
            "回复",
            {"topic": "主题A", "progress": "新进度", "next_step": "新下一步"},
            now=1001,
        )
    assert repo.view("one", now=1002)["turns"][0]["status"] == "pending"
    assert repo.active_topic("one")["progress"] == "尚未开始讨论。"


def test_old_topic_context_survives_many_messages_in_other_topics(setup):
    repo, materials = setup
    repo.create_topic("one", "主题A")
    a = repo.active_topic("one")["topic_id"]
    send(repo, "A以前学过的问题", now=1000)
    repo.create_topic("one", "主题B")
    for i in range(45):
        send(repo, f"B的问题{i}", now=1001 + i)
    seen = []

    def responder(history, message, learning, **kwargs):
        seen.extend(history)
        return CoachAnswer("接回 A。")

    assert (
        send(
            repo,
            "",
            action="continue",
            study_id=a,
            materials=materials,
            responder=responder,
            now=1100,
        )
        == "complete"
    )
    assert [m["content"] for m in seen] == ["A以前学过的问题", "好。"]
    assert len(repo.view("one", now=1101)["turns"]) == 40


def test_export_includes_all_owned_topic_positions_outside_chat_period_and_escapes_html(
    setup,
):
    repo, materials = setup
    book = materials.add("one", "book.txt", b"own book", title="本人资料")
    repo.create_topic("one", "<script>主题A</script>", book, now=1000)
    repo.create_topic("one", "主题B", now=1001)
    repo.create_topic("two", "another-user-private-topic", now=1002)
    archive = build_export(
        repo.database_path,
        materials.database_path,
        "one",
        ["chat"],
        period="30",
        now=4000000,
    )
    try:
        with ZipFile(archive.file) as zipped:
            text = zipped.read("学习主题/记录/学习主题目录.txt").decode()
            html = zipped.read("学习主题/记录/学习主题目录.html").decode()
            assert "主题B" in text and "本人资料" in text
            assert "another-user-private-topic" not in text
            assert "&lt;script&gt;主题A&lt;/script&gt;" in html
            assert "<script>主题A</script>" not in html
    finally:
        archive.file.close()
