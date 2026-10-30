import io
import secrets
import smtplib
import sqlite3
from zipfile import ZipFile

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from api import library_pages
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from security.passwords import hash_password
from tests.test_web_coach_dialogue import add_user, login, Forms, PASSWORD, BASE


@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("no SMTP or AI calls during exports")

    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def setup(tmp_path, password_hash):
    one = add_user(tmp_path, password_hash, "one@example.com", "导出体验者")
    two = add_user(tmp_path, password_hash, "two@example.com", "另一位用户")
    coach = CoachRepository(tmp_path / "coach_conversations.db")
    materials = MaterialRepository(tmp_path / "coach_library.db")
    for user, label in [(one, "one-owned"), (two, "two-private")]:
        nonce = secrets.token_urlsafe(32)
        coach.claim(user.user_id, nonce, label + "-question", now=1000)
        coach.finish(
            user.user_id,
            nonce,
            label + "-answer",
            None,
            now=1000,
            draft={
                "title": label + "-lesson",
                "topic": "学习",
                "content": "## " + label + "-content",
            },
        )
        identity = coach.list_knowledge(user.user_id, status="pending")[0][
            "knowledge_id"
        ]
        coach.confirm_knowledge(user.user_id, identity)
        materials.add(
            user.user_id,
            "notes.txt",
            (label + "-original").encode(),
            title=label + "-material",
        )
    app = create_account_app(tmp_path)
    with TestClient(app, base_url=BASE) as client:
        yield app, client, one, two


def fields(client, scopes=None):
    csrf = Forms(client.get("/web/export").text).values("/web/export")["csrf"]
    return {"csrf": csrf, "period": "all", "scope": scopes or ["saved"]}


def test_export_requires_authentication_and_is_not_a_get_download(setup):
    _, client, _, _ = setup
    assert client.get("/web/export", follow_redirects=False).status_code == 303
    assert (
        client.post("/web/export", data={}, follow_redirects=False).status_code == 303
    )
    page = login(client)
    assert "导出我的学习资料" in page.text
    page = client.get("/web/export")
    assert (
        page.status_code == 200
        and "script-src" in page.headers["content-security-policy"]
    )
    assert "想保护整个成长空间？" in page.text
    assert "完整私有备份" in page.text
    assert "不能在正在运行的网页里直接执行" in page.text
    assert 'href="/web/help"' in page.text
    assert "下载所选学习资料" in page.text and "checked" in page.text
    assert "application/zip" not in page.headers["content-type"]


def test_personal_download_is_owned_bounded_and_closes_tempfile(setup, monkeypatch):
    _, client, _, _ = setup
    login(client)
    created = []
    real = library_pages.build_export

    def build(*args, **kwargs):
        archive = real(*args, **kwargs)
        created.append(archive)
        return archive

    monkeypatch.setattr(library_pages, "build_export", build)
    response = client.post(
        "/web/export", data=fields(client, ["saved", "chat", "materials"])
    )
    assert response.status_code == 200 and response.headers["content-type"].startswith(
        "application/zip"
    )
    assert response.headers["cache-control"] == "no-store"
    assert int(response.headers["content-length"]) == len(response.content)
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    with ZipFile(io.BytesIO(response.content)) as archive:
        all_data = b"\n".join(archive.read(name) for name in archive.namelist())
        assert b"one-owned" in all_data and b"two-private" not in all_data
        assert b"$argon2id$" not in all_data
    assert created[0].file.closed


def test_csrf_is_session_bound_and_unknown_account_fields_are_rejected(setup):
    app, client, _, _ = setup
    login(client)
    original = fields(client)
    bad = client.post(
        "/web/export",
        data={**original, "csrf": "a" * 64},
        headers={"Accept": "application/json"},
    )
    assert bad.status_code == 403
    assert (
        client.post("/web/export", data={**original, "user_id": "another"}).status_code
        == 400
    )
    with TestClient(app, base_url=BASE) as other:
        login(other, "two@example.com")
        assert other.post("/web/export", data=original).status_code == 403
    assert (
        client.post(
            "/web/export", data=original, headers={"Origin": "https://outside.example"}
        ).status_code
        == 403
    )


@pytest.mark.parametrize(
    "change",
    [
        {"scope": ["saved", "saved"]},
        {"scope": ["unknown"]},
        {"period": "forever"},
        {"scope": []},
    ],
)
def test_invalid_export_choices_are_rejected(setup, change):
    _, client, _, _ = setup
    login(client)
    data = fields(client)
    data.update(change)
    assert client.post("/web/export", data=data).status_code == 400


def test_failure_is_redacted_and_next_export_still_works(setup, monkeypatch):
    _, client, _, _ = setup
    login(client)
    data = fields(client)

    def broken(*args, **kwargs):
        raise sqlite3.OperationalError("private-path-and-configuration")

    with monkeypatch.context() as patch:
        patch.setattr(library_pages, "build_export", broken)
        response = client.post(
            "/web/export", data=data, headers={"Accept": "application/json"}
        )
        assert response.status_code == 503 and "private-path" not in response.text
    assert client.post("/web/export", data=data).status_code == 200


def test_export_rate_limit_and_parser_limits(setup):
    _, client, _, _ = setup
    login(client)
    data = fields(client)
    assert (
        client.post(
            "/web/export",
            content=b"x" * 4097,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ).status_code
        == 400
    )
    assert client.post("/web/export", json=data).status_code == 400
    assert client.post("/web/export", data=data).status_code == 200
    assert client.post("/web/export", data=data).status_code == 200
    limited = client.post(
        "/web/export", data=data, headers={"Accept": "application/json"}
    )
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
