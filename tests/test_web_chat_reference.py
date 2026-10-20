import json
import secrets
import sqlite3
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from coach.materials import MaterialRepository
from tests import test_web_studies as base
from tests.test_coach_materials import pdf_bytes
from tests.test_conversation_review import turn, topic
from tests.test_web_coach_dialogue import BASE, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_paid_services = base.no_paid_services


class Anchors(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.items = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.items.append(dict(attrs))


def record(setup, *, raw=None):
    _, client, repo, materials, user, _, _ = setup
    login(client)
    book = materials.add(
        user.user_id,
        "notes.txt",
        (raw or "原文开头。\n\n先尝试回想，再核对资料。\n\n完整片段末尾。").encode(),
        title="当前改名后的资料",
    )
    chunk = materials.chunks(user.user_id, book)[0]
    source = dict(
        material_id=book,
        source_id=chunk["chunk_id"],
        title="回答时原来的书名",
        locator=chunk["locator"],
        excerpt=chunk["content"][5:19],
    )
    identity = turn(
        repo,
        "怎样回想再核对？",
        "## 尝试回想\n先说明，再验证。",
        user=user.user_id,
        citations=[source],
        now=1792411200,
    )
    return identity, source, book, chunk


def update_sources(repo, identity, sources):
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_turns SET citations_json=? WHERE turn_id=?",
            (json.dumps(sources, ensure_ascii=False), identity),
        )


def test_chat_and_readonly_full_question_reference_round_trip(setup):
    _, client, repo, materials, user, _, calls = setup
    identity, source, book, chunk = record(setup)
    current_book = materials.add(
        user.user_id, "other.txt", b"CURRENT_TOPIC", title="当前沟通资料"
    )
    assert repo.create_topic(user.user_id, "当前沟通主题", current_book) == "created"
    current = repo.active_topic(user.user_id)["topic_id"]
    # This unrelated selection must not replace the source retained on the answer.
    before = {p: p.read_bytes() for p in (repo.database_path, materials.database_path)}
    path = f"/web/conversations/{identity}/sources/1"
    chat = client.get("/web/welcome")
    links = [a for a in Anchors(chat.text).items if a.get("href") == path]
    assert links and all(
        a.get("target") == "_blank" and a.get("rel") == "noopener" for a in links
    )
    found = client.get(path)
    assert found.status_code == 200 and "核对对话引用" in found.text
    assert source["title"] in found.text and "当前改名后的资料" in found.text
    assert source["excerpt"] in found.text and "完整片段末尾。" in found.text
    assert "回答时保存的摘录" in found.text and "未归入学习主题" in found.text
    back = next(
        link for link in Links(found.text).links if "#dialogue-source-1" in link
    )
    returned = client.get(back)
    assert (
        'id="dialogue-source-1"' in returned.text
        and "怎样回想再核对？" in returned.text
    )
    assert "<h2>尝试回想</h2>" in returned.text
    assert (
        f"/web/materials/{book}?part={chunk['chunk_index']}" in Links(found.text).links
    )
    assert repo.active_topic(user.user_id)["topic_id"] == current
    assert all(p.read_bytes() == value for p, value in before.items()) and calls == []
    assert (
        found.headers["cache-control"] == "no-store"
        and found.headers["referrer-policy"] == "no-referrer"
    )


def test_history_lookup_filters_and_citation_anchor_are_preserved(setup):
    _, client, repo, _, user, _, _ = setup
    scope = topic(repo, "以前的学习主题", user=user.user_id)
    identity, _, _, _ = record(setup)
    values = dict(
        q="回想&核对", topic=scope, page="2", start="2026-10-19", end="2026-10-20"
    )
    detail = client.get(f"/web/conversations/{identity}", params=values)
    path = next(
        link for link in Links(detail.text).links if f"/{identity}/sources/1?" in link
    )
    assert parse_qs(urlsplit(path).query) == {
        key: [value] for key, value in values.items()
    }
    found = client.get(path)
    assert found.status_code == 200 and "以前的学习主题" in found.text
    back = next(
        link for link in Links(found.text).links if "#dialogue-source-1" in link
    )
    assert parse_qs(urlsplit(back).query) == {
        key: [value] for key, value in values.items()
    }
    assert urlsplit(back).fragment == "dialogue-source-1"
    returned = client.get(back)
    result = next(
        link
        for link in Links(returned.text).links
        if link.startswith("/web/conversations?")
    )
    assert parse_qs(urlsplit(result).query) == {
        key: [value] for key, value in values.items()
    }


def test_multiple_sources_use_the_selected_snapshot_not_a_different_book(setup):
    _, client, repo, materials, user, _, _ = setup
    identity, first, _, _ = record(setup)
    second_book = materials.add(
        user.user_id, "second.txt", "第二本书原文".encode(), title="第二本书"
    )
    chunk = materials.chunks(user.user_id, second_book)[0]
    second = dict(
        material_id=second_book,
        source_id=chunk["chunk_id"],
        title="第二本旧名",
        locator=chunk["locator"],
        excerpt="第二本书原文",
    )
    update_sources(repo, identity, [first, second])
    found = client.get(f"/web/conversations/{identity}/sources/2")
    assert found.status_code == 200 and second["excerpt"] in found.text
    assert "回答时原来的书名" not in found.text and "原文开头。" not in found.text
    assert "#dialogue-source-2" in found.text


@pytest.mark.parametrize(
    "change", ["legacy", "missing-material", "missing-chunk", "foreign", "wrong-book"]
)
def test_unavailable_sources_keep_snapshot_and_never_guess_or_leak(setup, change):
    _, client, repo, materials, user, other, _ = setup
    identity, source, _, _ = record(setup)
    private = materials.add(other.user_id, "private.txt", b"PRIVATE_FOREIGN_TEXT")
    private_chunk = materials.chunks(other.user_id, private)[0]
    own = materials.add(user.user_id, "another.txt", b"WRONG_BOOK_TEXT")
    if change == "legacy":
        source.pop("source_id")
    elif change == "missing-material":
        source["material_id"] = "a" * 32
    elif change == "missing-chunk":
        source["source_id"] = "b" * 32
    elif change == "foreign":
        source.update(material_id=private, source_id=private_chunk["chunk_id"])
    else:
        source["source_id"] = materials.chunks(user.user_id, own)[0]["chunk_id"]
    source["excerpt"] = "历史摘录依然可读"
    update_sources(repo, identity, [source])
    before = {p: p.read_bytes() for p in (repo.database_path, materials.database_path)}
    found = client.get(f"/web/conversations/{identity}/sources/1")
    assert found.status_code == 200 and "对应原文暂不可用" in found.text
    assert source["excerpt"] in found.text and "不按名称或文字猜测来源" in found.text
    assert (
        "PRIVATE_FOREIGN_TEXT" not in found.text and "WRONG_BOOK_TEXT" not in found.text
    )
    assert not any("?part=" in link for link in Links(found.text).links)
    assert all(p.read_bytes() == value for p, value in before.items())


def test_guest_other_account_and_different_topic_are_hidden(setup):
    app, client, repo, _, user, _, _ = setup
    identity, _, _, _ = record(setup)
    path = f"/web/conversations/{identity}/sources/1"
    with TestClient(app, base_url=BASE) as stranger:
        assert stranger.get(path, follow_redirects=False).status_code == 303
        login(stranger, "two@example.com")
        response = stranger.get(path)
        assert response.status_code == 404 and "原文开头。" not in response.text
    other = topic(repo, "另一个主题", user=user.user_id)
    assert client.get(path, params={"topic": other}).status_code == 404
    assert client.get(path, params={"topic": "unfiled"}).status_code == 200


@pytest.mark.parametrize(
    "identity,number",
    [
        ("0", "1"),
        ("01", "1"),
        ("-1", "1"),
        ("9223372036854775808", "1"),
        ("1", "0"),
        ("1", "-1"),
        ("1", "01"),
        ("1", "999"),
        ("1", "1000"),
    ],
)
def test_invalid_record_or_source_numbers_are_rejected(setup, identity, number):
    _, client, _, _, _, _, _ = setup
    record(setup)
    assert (
        client.get(f"/web/conversations/{identity}/sources/{number}").status_code == 404
    )


@pytest.mark.parametrize(
    "query",
    [
        "q=x&q=y",
        "topic=not-valid",
        "page=0",
        "start=wrong",
        "start=2026-10-20&end=2026-10-19",
        "user_id=other",
        "return=https://example.com",
    ],
)
def test_invalid_or_unexpected_lookup_parameters_are_rejected(setup, query):
    _, client, _, _, _, _, _ = setup
    identity, _, _, _ = record(setup)
    assert (
        client.get(f"/web/conversations/{identity}/sources/1?" + query).status_code
        == 400
    )


@pytest.mark.parametrize("state", ["pending", "failed", "complete"])
def test_turns_without_stored_sources_have_no_reference(setup, state):
    _, client, repo, _, user, _, _ = setup
    login(client)
    identity = turn(repo, "无引用问答", user=user.user_id, status=state)
    before = repo.database_path.read_bytes()
    assert client.get(f"/web/conversations/{identity}/sources/1").status_code == 404
    assert repo.database_path.read_bytes() == before


def test_original_title_locator_and_text_are_only_escaped_plain_text(setup):
    _, client, repo, _, _, _, _ = setup
    raw = "<script>不能执行</script>\n<img src=x onerror=alert(1)>"
    identity, source, _, _ = record(setup, raw=raw)
    source.update(title="<iframe>旧书名", locator="<img>位置", excerpt=raw)
    update_sources(repo, identity, [source])
    response = client.get(
        f"/web/conversations/{identity}/sources/1", params={"q": "<script>"}
    )
    assert response.status_code == 200 and Links(response.text).active == []
    assert (
        "&lt;script&gt;不能执行" in response.text
        and "&lt;iframe&gt;旧书名" in response.text
    )
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_mismatched_excerpt_is_not_marked_as_verified(setup):
    _, client, repo, _, _, _, _ = setup
    identity, source, _, _ = record(setup)
    source["excerpt"] = "无法与当前片段完全对上的文字"
    update_sources(repo, identity, [source])
    found = client.get(f"/web/conversations/{identity}/sources/1")
    assert (
        found.status_code == 200
        and "未能完全对上" in found.text
        and source["excerpt"] in found.text
    )


def test_material_failure_retains_snapshot_and_recovers_without_internal_details(
    setup, monkeypatch
):
    _, client, _, _, _, _, _ = setup
    identity, source, _, _ = record(setup)
    path = f"/web/conversations/{identity}/sources/1"
    original = MaterialRepository.chunk

    def broken(*a, **k):
        raise sqlite3.OperationalError("SECRET_INTERNAL_PATH")

    monkeypatch.setattr(MaterialRepository, "chunk", broken)
    response = client.get(path)
    assert response.status_code == 503 and source["excerpt"] in response.text
    assert "SECRET_INTERNAL_PATH" not in response.text
    monkeypatch.setattr(MaterialRepository, "chunk", original)
    assert client.get(path).status_code == 200


def test_reading_does_not_expire_other_pending_reply_or_increase_ai_usage(setup):
    _, client, repo, _, user, _, calls = setup
    identity, _, _, _ = record(setup)
    nonce = secrets.token_urlsafe(32)
    assert (
        repo.claim(
            user.user_id, nonce, "另一个尚未完成的问题", now=1, ai_kind="dialogue"
        )
        == "claimed"
    )
    before = repo.database_path.read_bytes()
    assert client.get(f"/web/conversations/{identity}/sources/1").status_code == 200
    assert repo.database_path.read_bytes() == before and calls == []


def test_pdf_reference_retains_real_extracted_page_and_preview_location(setup):
    _, client, repo, materials, user, _, _ = setup
    login(client)
    book = materials.add(user.user_id, "guide.pdf", pdf_bytes())
    chunk = materials.chunks(user.user_id, book)[0]
    source = dict(
        material_id=book,
        source_id=chunk["chunk_id"],
        title="PDF原名",
        locator=chunk["locator"],
        excerpt=chunk["content"],
    )
    identity = turn(repo, "PDF问题", user=user.user_id, citations=[source])
    response = client.get(f"/web/conversations/{identity}/sources/1")
    assert response.status_code == 200 and chunk["locator"] in response.text
    assert "PDF 第 1 页" in response.text and chunk["content"] in response.text
    assert f"/web/materials/{book}?part=1" in Links(response.text).links


def test_more_than_forty_turns_history_has_exact_source_links_without_javascript_number_rounding(
    setup,
):
    _, client, repo, _, user, _, _ = setup
    identity, _, _, _ = record(setup)
    for index in range(42):
        turn(repo, f"后来的讨论{index}", user=user.user_id, now=1792411300 + index * 2)
    page = repo.view(user.user_id)
    older = client.get("/web/coach/history", params={"before": page["before"]}).json()
    old = next(row for row in older["turns"] if row["turn_id"] == identity)
    assert old["citation_links"] == [f"/web/conversations/{identity}/sources/1"]
    huge = 9007199254740993
    with repo._connect() as db:
        db.execute("UPDATE coach_turns SET turn_id=? WHERE turn_id=?", (huge, identity))
    older = client.get("/web/coach/history", params={"before": str(huge + 1)}).json()
    old = next(row for row in older["turns"] if row["turn_id"] == huge)
    assert old["citation_links"] == [f"/web/conversations/{huge}/sources/1"]
    assert client.get(old["citation_links"][0]).status_code == 200


def test_right_learning_panel_links_to_the_active_topics_latest_actual_answer(setup):
    _, client, repo, _, user, _, _ = setup
    scope = topic(repo, "原主题", user=user.user_id)
    identity, _, _, _ = record(setup)
    topic(repo, "另一个主题", user=user.user_id, now=1792411300)
    later = turn(repo, "别的主题问题", user=user.user_id, now=1792411400)
    repo.activate_topic(user.user_id, scope)
    page = client.get("/web/welcome")
    right = page.text.split('id="workspace-learning"', 1)[1]
    assert f"/web/conversations/{identity}/sources/1" in right
    assert f"/web/conversations/{later}/sources/" not in right
