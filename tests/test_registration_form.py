import hashlib
import smtplib
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from security.auth import initialize_user_password, verify_user_password
from security.registration_validation import validate_registration_fields
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


PASSWORD = "a quiet place to learn"


class Elements(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.elements = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


@pytest.fixture
def client(tmp_path, monkeypatch):
    def forbid_mail(*args, **kwargs):
        raise AssertionError("form preview must never connect to mail")

    monkeypatch.setattr(smtplib, "SMTP_SSL", forbid_mail)
    monkeypatch.setattr(smtplib, "SMTP", forbid_mail)
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app) as client:
        yield client


def test_get_form_supports_basic_browser_validation_but_login_stays_closed(client):
    response = client.get("/web/register")
    elements = Elements(response.text).elements
    inputs = {a["name"]: a for tag, a in elements if tag == "input"}
    assert inputs["name"]["maxlength"] == "40"
    assert inputs["email"]["type"] == "email"
    assert inputs["password"]["type"] == "password"
    assert inputs["password"]["autocomplete"] == "new-password"
    assert inputs["password"]["minlength"] == "15"
    assert inputs["password"]["maxlength"] == "128"
    assert "value" not in inputs["password"]
    assert not any(
        "disabled" in a for tag, a in elements if tag in {"fieldset", "button", "input"}
    )
    assert "检查填写并继续" in response.text
    assert "请使用测试资料" in response.text
    assert "disabled" in client.get("/web/login").text
    assert (
        client.post(
            "/web/auth/login",
            data={"email": "learner@example.com", "password": PASSWORD},
        ).status_code
        == 503
    )


@pytest.mark.parametrize("name", ["", "测试成长者"])
def test_valid_submission_goes_to_honest_masked_waiting_page_without_writes(
    client, tmp_path, name
):
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*.db")
    }
    response = client.post(
        "/web/auth/register",
        data={"name": name, "email": "learner@example.com", "password": PASSWORD},
    )
    assert response.status_code == 200
    assert "下一步，验证你的邮箱" in response.text
    assert "l***@example.com" in response.text
    assert "learner@example.com" not in response.text
    assert PASSWORD not in response.text
    assert "本次尚未发送邮件，也未创建账户" in response.text
    assert "无需等待邮件" in response.text
    assert "已发送至" not in response.text
    assert "set-cookie" not in response.headers
    assert not any(tag == "form" for tag, _ in Elements(response.text).elements)
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == digest
        for p, digest in before.items()
    )


@pytest.mark.parametrize(
    "password,valid",
    [
        ("x" * 14, False),
        ("x" * 15, True),
        ("x" * 128, True),
        ("x" * 129, False),
        (" " * 15, False),
        ("好" * 15, True),
        (" a quiet place to learn ", True),
    ],
)
def test_password_policy_matches_existing_hashing_input_limits(client, password, valid):
    response = client.post(
        "/web/auth/register",
        data={"name": "测试", "email": "learner@example.com", "password": password},
    )
    assert response.status_code == (200 if valid else 400)
    if password.strip():
        assert password not in response.text
    elements = Elements(response.text).elements
    assert all(
        "value" not in a
        for tag, a in elements
        if tag == "input" and a.get("type") == "password"
    )
    if not valid:
        assert "register-password-error" in response.text
        assert 'aria-invalid="true"' in response.text


@pytest.mark.parametrize(
    "email",
    [
        "",
        "bad",
        "a@localhost",
        "a@@example.com",
        "a..b@example.com",
        "Name <a@example.com>",
        "a@example.com,b@example.com",
        "a@-bad.example",
        "a@example..com",
        "a@example.com\r\nBcc:b@example.com",
        "a@ex ample.com",
        "a" * 65 + "@example.com",
    ],
)
def test_invalid_addresses_get_field_errors_without_mail_or_password_echo(
    client, email
):
    response = client.post(
        "/web/auth/register",
        data={"name": "测试", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 400
    assert "register-email-error" in response.text
    assert PASSWORD not in response.text


def test_name_and_email_are_retained_escaped_on_password_error(client):
    name = '<img src=x onerror="alert(1)">'
    email = "learner@example.com"
    response = client.post(
        "/web/auth/register",
        data={"name": name, "email": email, "password": "short-secret"},
    )
    assert response.status_code == 400
    assert "short-secret" not in response.text
    elements = Elements(response.text).elements
    inputs = {a["name"]: a for tag, a in elements if tag == "input"}
    assert inputs["name"]["value"] == name
    assert inputs["email"]["value"] == email
    assert not any(tag in {"img", "script", "iframe"} for tag, _ in elements)
    assert "value" not in inputs["password"]
    ids = {a["id"] for _, a in elements if "id" in a}
    for tag, a in elements:
        if tag == "a" and a.get("href", "").startswith("#"):
            assert a["href"][1:] in ids


@pytest.mark.parametrize("name", ["名" * 41, "name\nnewline", "name\x00control"])
def test_name_length_and_control_characters_are_checked(client, name):
    response = client.post(
        "/web/auth/register",
        data={"name": name, "email": "learner@example.com", "password": PASSWORD},
    )
    assert response.status_code == 400
    assert "register-name-error" in response.text
    assert PASSWORD not in response.text


@pytest.mark.parametrize(
    "body,kind",
    [
        ('{"password":"do-not-echo"}', "application/json"),
        ("password=do-not-echo&password=other", "application/x-www-form-urlencoded"),
        ("email=%FF&password=do-not-echo", "application/x-www-form-urlencoded"),
        (
            "email=a%40example.com&password=do-not-echo&token=a&csrf=b",
            "application/x-www-form-urlencoded",
        ),
        ("password=" + "a" * 9000, "application/x-www-form-urlencoded"),
    ],
)
def test_malformed_and_large_requests_are_not_echoed(client, body, kind):
    response = client.post(
        "/web/auth/register", content=body, headers={"Content-Type": kind}
    )
    assert response.status_code == 400
    assert "text/html" in response.headers["content-type"]
    assert "do-not-echo" not in response.text
    assert "无法读取" in response.text


def test_missing_inputs_are_form_errors_instead_of_api_validation_details(client):
    response = client.post("/web/auth/register", data={"name": "测试"})
    assert response.status_code == 400
    assert "register-email-error" in response.text
    assert "register-password-error" in response.text
    assert '"detail"' not in response.text


def test_preview_cannot_change_an_existing_password_or_verification(client, tmp_path):
    repository = SQLiteUserRepository(tmp_path / "users.db")
    user = User(name="原来的称呼", email="learner@example.com")
    repository.save(user)
    initialize_user_password(repository, user.user_id, PASSWORD)
    original_hash = repository.get_password_hash(user.user_id)
    response = client.post(
        "/web/auth/register",
        data={
            "name": "不同的称呼",
            "email": user.email,
            "password": "a different quiet password",
        },
    )
    assert response.status_code == 200
    assert repository.get_by_id(user.user_id).name == "原来的称呼"
    assert repository.get_password_hash(user.user_id) == original_hash
    assert verify_user_password(repository, user.user_id, PASSWORD)
    assert not repository.is_email_verified(user.user_id)
    assert "set-cookie" not in response.headers


def test_responses_are_private_and_have_only_local_navigation(client):
    for password in [PASSWORD, "short"]:
        response = client.post(
            "/web/auth/register",
            data={"email": "learner@example.com", "password": password},
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert response.headers["x-frame-options"] == "DENY"
        for tag, a in Elements(response.text).elements:
            if tag == "a":
                assert a["href"].startswith(("/", "#"))
                if a["href"].startswith("/"):
                    assert client.get(a["href"]).status_code == 200
            if tag == "link":
                assert client.get(a["href"]).status_code == 200


def test_validation_result_never_carries_password_and_normalizes_editable_fields():
    checked = validate_registration_fields(
        "  测试  ", " Learner@Example.COM ", PASSWORD
    )
    assert checked == {"name": "测试", "email": "learner@example.com", "errors": {}}
    assert PASSWORD not in repr(checked)
