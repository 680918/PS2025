import sqlite3
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from api.app import create_app


class PageElements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.fixture
def client(tmp_path):
    app = create_app(
        database_dir=tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    return TestClient(app)


@pytest.mark.parametrize("path", ["/", "/web/login", "/web/register"])
def test_public_pages_have_working_local_navigation_and_styles(client, path):
    response = client.get(path)
    assert response.status_code == 200
    assert '<meta name="viewport"' in response.text
    assert "注册与登录尚未开放" in response.text
    assert "手机号" not in response.text
    assert "短信" not in response.text

    elements = PageElements(response.text).elements
    ids = {attrs["id"] for _, attrs in elements if "id" in attrs}
    for tag, attrs in elements:
        if tag == "a":
            href = attrs["href"]
            assert href.startswith("/") or href.startswith("#")
            if href.startswith("#"):
                assert href[1:] in ids
            else:
                assert client.get(href).status_code == 200
        if tag == "link":
            asset = client.get(attrs["href"])
            assert asset.status_code == 200
            assert "text/css" in asset.headers["content-type"]
        assert tag not in {"script", "iframe"}


@pytest.mark.parametrize(
    ("path", "autocomplete"),
    [("/web/login", "current-password")],
)
def test_email_fields_and_submit_are_disabled_until_auth_is_ready(
    client, path, autocomplete
):
    response = client.get(path)
    elements = PageElements(response.text).elements
    assert any(tag == "fieldset" and "disabled" in a for tag, a in elements)
    assert any(tag == "button" and "disabled" in a for tag, a in elements)
    assert any(tag == "input" and a.get("type") == "email" for tag, a in elements)
    passwords = [a for tag, a in elements if a.get("type") == "password"]
    assert len(passwords) == 1
    assert passwords[0]["autocomplete"] == autocomplete
    assert "value" not in passwords[0]
    assert 'type="tel"' not in response.text


@pytest.mark.parametrize("path", ["/web/auth/login"])
def test_unavailable_auth_never_creates_account_or_returns_credentials(
    client, tmp_path, path
):
    password = "test-only-secret-not-for-storage"
    response = client.post(
        path,
        data={"name": "测试", "email": "not-created@example.com", "password": password},
    )
    assert response.status_code == 503
    assert "尚未开放" in response.text
    assert password not in response.text
    assert "not-created@example.com" not in response.text
    assert "set-cookie" not in response.headers
    with sqlite3.connect(tmp_path / "users.db") as connection:
        assert connection.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


def test_pages_and_assets_are_independent_of_shell_working_directory(
    client, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert client.get("/web/login").status_code == 200
    response = client.get("/static/public.css")
    assert response.status_code == 200
    assert "@media" in response.text
