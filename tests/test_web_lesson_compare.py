import secrets
import sqlite3
from html import escape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient

from api.library_pages import lesson_difference
from conversation.coach_repository import CoachRepository
from tests import test_web_lesson_revision as base
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import BASE, Forms, login
from tests.test_web_knowledge_search import Links

setup = base.setup
password_hash = base.password_hash
no_real_services = base.no_real_services


class DifferenceLines(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.labels = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "div" and "lesson-diff-line" in values.get("class", "").split():
            self.labels.append(values["class"])


def two_versions(setup):
    _, _, repo, user, identity = setup
    assert (
        repo.revise_knowledge(
            user.user_id,
            identity,
            1,
            title="修订后标题",
            content="# 原文\n换一个自己的例子。\n补充核对步骤。",
        )
        == "updated"
    )
    return f"/web/knowledge/{identity}"


def compare_link(text):
    return next(link for link in Links(text).links if "/compare?" in link)


def test_history_entry_readonly_diff_and_original_version_restore_entry(setup):
    _, client, repo, user, identity = setup
    path = two_versions(setup)
    current = repo.active_topic(user.user_id)
    before = repo.database_path.read_bytes()
    history = client.get(path + "/versions")
    # Current card compares the last two explicit version numbers.
    link = compare_link(history.text)
    assert parse_qs(urlsplit(link).query) == dict(base=["1"], target=["2"], page=["1"])
    response = client.get(link)
    assert response.status_code == 200 and "教案版本对比" in response.text
    assert "原版教案" in response.text and "修订后标题" in response.text
    assert "标题有变化" in response.text and "正文新增 2 行、移除 1 行" in response.text
    assert "− 移除" in response.text and "+ 新增" in response.text
    assert "最初的例子。" in response.text and "换一个自己的例子。" in response.text
    assert path + "/versions/1" in Links(response.text).links
    assert path + "/versions/2" in Links(response.text).links
    assert path + "/versions?page=1" in Links(response.text).links
    forms = Forms(response.text).forms
    assert not any(form["path"].endswith(("/restore", "/revise")) for form in forms)
    # Existing restore still requires an explicit, bound POST on the old-version page.
    old = client.get(path + "/versions/1")
    assert (
        "确认恢复第 1 版内容" in old.text and "/compare?base=1&amp;target=2" in old.text
    )
    latest = client.get(path + "/versions/2")
    assert "查看与上一版的差异 →" in latest.text
    assert "/compare?base=1&amp;target=2" in latest.text
    assert repo.database_path.read_bytes() == before
    assert repo.active_topic(user.user_id) == current
    assert repo.knowledge(user.user_id, identity)["revision"] == 2
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_title_only_edit_body_unchanged_and_same_version_are_honest(setup):
    _, client, repo, user, identity = setup
    original = repo.knowledge(user.user_id, identity)
    assert (
        repo.revise_knowledge(
            user.user_id, identity, 1, title="只改标题", content=original["content"]
        )
        == "updated"
    )
    path = f"/web/knowledge/{identity}/compare"
    response = client.get(path, params={"base": 1, "target": 2})
    assert "标题有变化" in response.text and "两版正文相同" in response.text
    assert "正文新增 0 行、移除 0 行" in response.text
    same = client.get(path, params={"base": 2, "target": 2})
    assert (
        same.status_code == 200
        and "标题相同" in same.text
        and "两版正文相同" in same.text
    )
    assert DifferenceLines(same.text).labels == []


def test_first_saved_lesson_without_revision_rows_can_compare_to_itself(setup):
    _, client, repo, _, identity = setup
    before = repo.database_path.read_bytes()
    page = client.get(f"/web/knowledge/{identity}/compare?base=1&target=1")
    assert page.status_code == 200 and "两版正文相同" in page.text
    assert repo.database_path.read_bytes() == before


def test_explicit_old_pair_remains_fixed_after_later_revision_and_restore(setup):
    _, client, repo, user, identity = setup
    path = two_versions(setup)
    link = compare_link(client.get(path + "/versions").text)
    assert (
        repo.revise_knowledge(
            user.user_id,
            identity,
            2,
            title="后来第三版标题",
            content="LATER_BODY_DO_NOT_COMPARE",
        )
        == "updated"
    )
    assert repo.revise_knowledge(user.user_id, identity, 3, restore=1) == "updated"
    page = client.get(link)
    assert page.status_code == 200 and "换一个自己的例子。" in page.text
    assert "LATER_BODY_DO_NOT_COMPARE" not in page.text
    assert 'name="base"' in page.text and 'value="2"' in page.text
    restored = client.get(path + "/compare?base=1&target=4")
    assert "两版正文相同" in restored.text and "标题相同" in restored.text
    assert repo.knowledge(user.user_id, identity)["revision"] == 4


def test_reverse_comparison_changes_add_and_remove_direction(setup):
    _, client, _, _, _ = setup
    path = two_versions(setup)
    response = client.get(path + "/compare?base=2&target=1")
    assert response.status_code == 200 and "正文新增 1 行、移除 2 行" in response.text
    assert "原第 3 行" in response.text and "对照第 2 行" in response.text


def test_version_directory_page_is_retained_and_any_existing_pair_can_be_chosen(setup):
    _, client, repo, user, identity = setup
    for revision in range(1, 24):
        assert (
            repo.revise_knowledge(
                user.user_id,
                identity,
                revision,
                title=f"版本{revision + 1}",
                content=f"正文{revision + 1}",
            )
            == "updated"
        )
    path = f"/web/knowledge/{identity}"
    history = client.get(path + "/versions?page=2")
    link = compare_link(history.text)
    assert parse_qs(urlsplit(link).query)["page"] == ["2"]
    compared = client.get(link)
    assert path + "/versions?page=2" in Links(compared.text).links
    other_pair = client.get(path + "/compare?base=3&target=19&page=2")
    assert (
        other_pair.status_code == 200
        and "正文3" in other_pair.text
        and "正文19" in other_pair.text
    )
    assert 'name="page" value="2"' in other_pair.text


def test_guest_other_account_pending_and_dismissed_lessons_cannot_be_compared(setup):
    app, client, repo, user, identity = setup
    path = f"/web/knowledge/{identity}/compare?base=1&target=1"
    with TestClient(app, base_url=BASE) as other:
        assert other.get(path, follow_redirects=False).status_code == 303
        login(other, "two@example.com")
        assert other.get(path).status_code == 404
    pending = saved_lesson(repo, user.user_id, save=False)
    assert (
        client.get(f"/web/knowledge/{pending}/compare?base=1&target=1").status_code
        == 404
    )
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_knowledge SET status='dismissed' WHERE knowledge_id=?",
            (pending,),
        )
    assert (
        client.get(f"/web/knowledge/{pending}/compare?base=1&target=1").status_code
        == 404
    )


@pytest.mark.parametrize(
    "query",
    [
        "",
        "base=1",
        "base=1&target=0",
        "base=01&target=1",
        "base=-1&target=1",
        "base=1&target=1.0",
        "base=1&target=1000000001",
        "base=1&target=1&target=2",
        "base=1&target=1&page=0",
        "base=1&target=1&page=100001",
        "base=1&target=1&page=1&page=2",
        "base=1&target=1&user_id=someone",
        "base=1&target=1&return=https://example.com",
    ],
)
def test_invalid_duplicate_or_unexpected_comparison_parameters_are_rejected(
    setup, query
):
    _, client, repo, _, identity = setup
    before = repo.database_path.read_bytes()
    assert client.get(f"/web/knowledge/{identity}/compare?" + query).status_code == 400
    assert repo.database_path.read_bytes() == before


@pytest.mark.parametrize("base_number,target", [(2, 1), (1, 999)])
def test_missing_versions_are_not_replaced_by_current_content(
    setup, base_number, target
):
    _, client, _, _, identity = setup
    response = client.get(
        f"/web/knowledge/{identity}/compare?base={base_number}&target={target}"
    )
    assert response.status_code == 404 and "最初的例子" not in response.text


def test_titles_html_tables_and_code_are_escaped_and_indentation_preserved(setup):
    _, client, repo, user, identity = setup
    content = "<script>不执行</script>\n| 列 |\n| --- |\n```python\nif ready:\n    review()\n```"
    assert (
        repo.revise_knowledge(
            user.user_id,
            identity,
            1,
            title="<img src=x onerror=alert(1)>",
            content=content,
        )
        == "updated"
    )
    response = client.get(f"/web/knowledge/{identity}/compare?base=1&target=2")
    assert response.status_code == 200 and Links(response.text).active == []
    assert escape("<script>不执行</script>") in response.text
    assert "    review()\n</pre>" in response.text
    assert "| 列 |" in response.text and "<table>" not in response.text
    assert "default-src 'none'" in response.headers["content-security-policy"]


def test_database_error_does_not_leak_details_and_recovery_is_readonly(
    setup, monkeypatch
):
    _, client, repo, _, identity = setup
    original = CoachRepository.knowledge_version

    def broken(*a, **k):
        raise sqlite3.OperationalError("PRIVATE_INTERNAL_DATABASE_PATH")

    monkeypatch.setattr(CoachRepository, "knowledge_version", broken)
    response = client.get(f"/web/knowledge/{identity}/compare?base=1&target=1")
    assert (
        response.status_code == 503
        and "PRIVATE_INTERNAL_DATABASE_PATH" not in response.text
    )
    monkeypatch.setattr(CoachRepository, "knowledge_version", original)
    assert (
        client.get(f"/web/knowledge/{identity}/compare?base=1&target=1").status_code
        == 200
    )


def test_other_pending_reply_is_not_expired_by_reading_comparison(setup):
    _, client, repo, user, identity = setup
    assert (
        repo.claim(
            user.user_id,
            secrets.token_urlsafe(32),
            "在途问题",
            now=1,
            ai_kind="dialogue",
        )
        == "claimed"
    )
    before = repo.database_path.read_bytes()
    assert (
        client.get(f"/web/knowledge/{identity}/compare?base=1&target=1").status_code
        == 200
    )
    assert repo.database_path.read_bytes() == before


def test_large_comparison_has_complete_counts_and_bounded_display(setup):
    _, client, repo, user, identity = setup
    first = "".join(f"原{i}\n" for i in range(600))
    second = "".join(f"新{i}\n" for i in range(600)).rstrip()
    with repo._connect() as db:
        db.execute(
            "UPDATE coach_knowledge SET content=? WHERE knowledge_id=?",
            (first, identity),
        )
    assert (
        repo.revise_knowledge(user.user_id, identity, 1, title="长版本", content=second)
        == "updated"
    )
    before = repo.database_path.read_bytes()
    response = client.get(f"/web/knowledge/{identity}/compare?base=1&target=2")
    assert (
        response.status_code == 200 and "正文新增 600 行、移除 600 行" in response.text
    )
    assert (
        len(DifferenceLines(response.text).labels) == 400
        and "仅展示前 400 行" in response.text
    )
    assert (
        "阅读本版完整内容" in response.text
        and repo.database_path.read_bytes() == before
    )


def test_complete_body_statistics_count_changes_beyond_the_display_limit():
    result, added, removed = lesson_difference("旧\n" * 2000, "新\n" * 2000)
    assert (added, removed) == (2000, 2000) and len(
        DifferenceLines(result).labels
    ) == 400


def test_blank_lines_line_endings_and_unchanged_context_are_preserved():
    result, added, removed = lesson_difference("前\n\n旧\n后\n", "前\n\n新\n后\n")
    assert (added, removed) == (1, 1) and "lesson-diff-same" in result
    result, added, removed = lesson_difference("相同文字\n", "相同文字")
    assert (added, removed) == (1, 1) and "行末无换行" in result


def test_invalid_lesson_identity_is_rejected_before_reading_versions(setup):
    _, client, _, _, _ = setup
    assert (
        client.get("/web/knowledge/not-a-lesson/compare?base=1&target=1").status_code
        == 404
    )


def test_maximum_length_unicode_line_is_preserved_without_executing_html():
    before = "😀" * 12000
    after = "🌱" * 11990 + "<script>x"
    result, added, removed = lesson_difference(before, after)
    assert (added, removed) == (1, 1)
    assert before in result and escape(after) in result
    assert Links(result).active == [] and "仅展示前 400 行" not in result
