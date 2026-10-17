import secrets
import smtplib
from time import time

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from conversation.coach_repository import CoachRepository
from security.passwords import hash_password
from tests.test_lesson_revision import saved_lesson
from tests.test_web_coach_dialogue import add_user, login, Forms, PASSWORD, BASE


@pytest.fixture(autouse=True)
def no_real_services(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No real mail or paid AI in revision QA")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def setup(tmp_path, password_hash):
    user = add_user(tmp_path, password_hash, "one@example.com", "教案修订体验者")
    add_user(tmp_path, password_hash, "two@example.com", "其他用户")
    repo = CoachRepository(tmp_path / "coach_conversations.db")
    identity = saved_lesson(repo, user.user_id)
    app = create_account_app(tmp_path)
    with TestClient(app, base_url=BASE) as client:
        login(client)
        yield app, client, repo, user, identity


def edit_fields(client, path):
    return Forms(client.get(path + "/edit").text).values(path + "/revise")


def test_edit_read_version_restore_and_download_work_without_ai(setup):
    _, client, repo, user, identity = setup
    path = "/web/knowledge/" + identity
    original = client.get(path)
    assert "修改教案" in original.text and "第 1 版" in original.text
    fields = edit_fields(client, path)
    saved = client.post(
        path + "/revise",
        data={
            **fields,
            "title": "新的标题",
            "content": "## 新内容\n补充一个生活例子。",
        },
    )
    assert (
        saved.status_code == 200
        and "修订已保存" in saved.text
        and "第 2 版" in saved.text
    )
    assert client.get(path + "/download").text == "## 新内容\n补充一个生活例子。"
    assert "原版教案" in client.get(path + "/versions").text
    old = client.get(path + "/versions/1")
    assert "最初的例子" in old.text and "历史版本" in old.text
    fields = Forms(old.text).values(path + "/restore")
    result = client.post(path + "/restore", data=fields)
    assert "第 3 版" in result.text and "原有版本均保留" in result.text
    assert repo.knowledge_version(user.user_id, identity, 2)["title"] == "新的标题"
    assert client.get(path + "/download").text == "# 原文\n最初的例子。"


def test_stale_editor_preserves_attempted_text_and_allows_explicit_merge(setup):
    _, client, repo, user, identity = setup
    path = "/web/knowledge/" + identity
    fields = edit_fields(client, path)
    repo.revise_knowledge(
        user.user_id, identity, 1, title="另一页标题", content="另一页已保存内容"
    )
    result = client.post(
        path + "/revise",
        data={
            **fields,
            "title": "未保存标题",
            "content": "<script>我的待合并内容</script>",
        },
    )
    assert result.status_code == 409
    assert "另一页已保存内容" in result.text and "未保存标题" in result.text
    assert (
        "&lt;script&gt;我的待合并内容&lt;/script&gt;" in result.text
        and "<script>" not in result.text
    )
    current_fields = Forms(result.text).values(path + "/revise")
    assert current_fields["revision"] == "2"
    merged = client.post(
        path + "/revise",
        data={**current_fields, "title": "合并标题", "content": "明确合并后的内容。"},
    )
    assert (
        merged.status_code == 200
        and repo.knowledge(user.user_id, identity)["revision"] == 3
    )


@pytest.mark.parametrize(
    "kind",
    [
        "csrf",
        "revision",
        "origin",
        "cross-site",
        "extra",
        "duplicate",
        "json",
        "oversize",
    ],
)
def test_rejects_forged_or_malformed_edits(setup, kind):
    _, client, repo, user, identity = setup
    path = "/web/knowledge/" + identity
    fields = {**edit_fields(client, path), "title": "新", "content": "新内容"}
    headers = {}
    if kind == "csrf":
        fields["csrf"] = "中" * 64
    if kind == "revision":
        fields["revision"] = "2"
    if kind == "origin":
        headers["origin"] = "https://outside.example"
    if kind == "cross-site":
        headers["sec-fetch-site"] = "cross-site"
    if kind == "extra":
        fields["user_id"] = user.user_id
    if kind == "oversize":
        fields["content"] = "字" * 60000
    if kind == "duplicate":
        result = client.post(
            path + "/revise",
            content="csrf=x&csrf=y&revision=1&title=x&content=y",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    elif kind == "json":
        result = client.post(path + "/revise", json=fields)
    else:
        result = client.post(path + "/revise", data=fields, headers=headers)
    assert result.status_code in {400, 403}
    assert repo.knowledge(user.user_id, identity)["revision"] == 1


def test_other_account_or_session_cannot_access_or_submit_versions(setup):
    app, client, _, _, identity = setup
    path = "/web/knowledge/" + identity
    fields = {**edit_fields(client, path), "content": "越权内容"}
    with TestClient(app, base_url=BASE) as other:
        assert other.get(path + "/edit", follow_redirects=False).status_code == 303
        login(other, "two@example.com")
        for suffix in ("/edit", "/versions", "/versions/1"):
            assert other.get(path + suffix).status_code == 404
        assert other.post(path + "/revise", data=fields).status_code == 403
    with TestClient(app, base_url=BASE) as another:
        login(another)
        assert another.post(path + "/revise", data=fields).status_code == 403


def test_restore_target_is_bound_and_stale_restore_requires_confirmation_again(setup):
    _, client, repo, user, identity = setup
    path = "/web/knowledge/" + identity
    repo.revise_knowledge(user.user_id, identity, 1, title="新版", content="新版正文")
    old = client.get(path + "/versions/1")
    fields = Forms(old.text).values(path + "/restore")
    assert (
        client.post(path + "/restore", data={**fields, "target": "2"}).status_code
        == 403
    )
    repo.revise_knowledge(
        user.user_id, identity, 2, title="又有更新", content="最新正文"
    )
    result = client.post(path + "/restore", data=fields)
    assert result.status_code == 409 and "请核对当前版本" in result.text
    assert repo.knowledge(user.user_id, identity)["revision"] == 3
    fields = Forms(result.text).values(path + "/restore")
    assert client.post(path + "/restore", data=fields).status_code == 200
    assert repo.knowledge(user.user_id, identity)["revision"] == 4
    assert client.post(path + "/restore", data=fields).status_code == 409
    assert repo.knowledge(user.user_id, identity)["revision"] == 4


def test_bad_lengths_keep_form_and_busy_review_does_not_modify_content(setup):
    _, client, repo, user, identity = setup
    path = "/web/knowledge/" + identity
    fields = edit_fields(client, path)
    invalid = client.post(
        path + "/revise", data={**fields, "title": "标题仍在", "content": " "}
    )
    assert (
        invalid.status_code == 200
        and "标题仍在" in invalid.text
        and "正文需要" in invalid.text
    )
    repo.select_review(user.user_id, identity)
    repo.claim(user.user_id, secrets.token_urlsafe(32), "正在重温", now=int(time()))
    result = client.post(
        path + "/revise",
        data={**fields, "title": "填写内容仍在", "content": "尚未保存的正文。"},
    )
    assert result.status_code == 409 and "尚未保存的正文" in result.text
    assert repo.knowledge(user.user_id, identity)["revision"] == 1


def test_opaque_same_origin_editor_and_version_pagination(setup):
    _, client, repo, user, identity = setup
    path = "/web/knowledge/" + identity
    fields = edit_fields(client, path)
    result = client.post(
        path + "/revise",
        data={**fields, "title": "<标题>", "content": "新内容"},
        headers={"origin": "null", "sec-fetch-site": "same-origin"},
    )
    assert result.status_code == 200 and "&lt;标题&gt;" in result.text
    assert result.headers["cache-control"] == "no-store"
    for revision in range(2, 24):
        repo.revise_knowledge(
            user.user_id,
            identity,
            revision,
            title=f"版{revision + 1}",
            content=f"内容{revision + 1}",
        )
    assert "下一页" in client.get(path + "/versions").text
    assert "首次保存" in client.get(path + "/versions?page=2").text
    assert client.get(path + "/versions/999").status_code == 404
    assert client.get(path + "/versions?page=bad").status_code == 400
