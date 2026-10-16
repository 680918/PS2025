import hashlib
import smtplib
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from api import registration_pages as pages
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


def form_token(html):
    return next(
        a["value"]
        for tag, a in Elements(html).elements
        if tag == "input" and a.get("name") == "csrf"
    )


def submit(client, *, data):
    csrf = form_token(client.get("/web/register").text)
    return client.post("/web/auth/register", data={**data, "csrf": csrf})


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
    response = submit(
        client,
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
    response = submit(
        client,
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
    response = submit(
        client,
        data={"name": "测试", "email": email, "password": PASSWORD},
    )
    assert response.status_code == 400
    assert "register-email-error" in response.text
    assert PASSWORD not in response.text


def test_name_and_email_are_retained_escaped_on_password_error(client):
    name = '<img src=x onerror="alert(1)">'
    email = "learner@example.com"
    response = submit(
        client,
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
    response = submit(
        client,
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
    client.get("/web/register")
    response = client.post(
        "/web/auth/register", content=body, headers={"Content-Type": kind}
    )
    assert response.status_code == 400
    assert "text/html" in response.headers["content-type"]
    assert "do-not-echo" not in response.text
    assert "无法读取" in response.text


def test_missing_inputs_are_form_errors_instead_of_api_validation_details(client):
    response = submit(client, data={"name": "测试"})
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
    response = submit(
        client,
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
        response = submit(
            client,
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


def test_get_sets_private_scoped_form_context_and_keeps_it_stable(client, monkeypatch):
    first = client.get("/web/register")
    csrf = form_token(first.text)
    assert len(csrf) == 43
    cookie = first.headers["set-cookie"]
    for flag in ("HttpOnly", "SameSite=strict", "Path=/web", "Max-Age=1800"):
        assert flag in cookie
    assert "Secure" not in cookie  # TestClient defaults to local HTTP.
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["referrer-policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in first.headers["content-security-policy"]
    before = client.cookies.get(pages._COOKIE)
    later = pages.time() + 60
    monkeypatch.setattr(pages, "time", lambda: later)
    second = client.get("/web/register")
    assert form_token(second.text) == csrf
    assert client.cookies.get(pages._COOKIE) == before
    assert "set-cookie" not in second.headers


@pytest.mark.parametrize(
    "case",
    [
        "missing-cookie",
        "tampered-cookie",
        "missing-csrf",
        "wrong-csrf",
        "non-ascii-csrf",
        "expired",
        "other-browser",
    ],
)
def test_csrf_failures_are_generic_and_rejected_before_field_validation(
    client, tmp_path, monkeypatch, case
):
    token = form_token(client.get("/web/register").text)
    data = {
        "csrf": token,
        "name": "private-name-only",
        "email": "private-only@example.com",
        "password": "private-password-only",
    }
    if case == "missing-cookie":
        client.cookies.clear()
    elif case == "tampered-cookie":
        original = client.cookies.get(pages._COOKIE)
        client.cookies.clear()
        client.cookies.set(
            pages._COOKIE, original[:-1] + ("1" if original[-1] != "1" else "2")
        )
    elif case == "missing-csrf":
        data.pop("csrf")
    elif case == "wrong-csrf":
        data["csrf"] = "a" * 43
    elif case == "non-ascii-csrf":
        data["csrf"] = "字" * 43
    elif case == "expired":
        later = pages.time() + 1800
        monkeypatch.setattr(pages, "time", lambda: later)
    elif case == "other-browser":
        original = client.cookies.get(pages._COOKIE)
        client.cookies.clear()
        client.get("/web/register")
        assert client.cookies.get(pages._COOKIE) != original

    def forbidden(*args, **kwargs):
        raise AssertionError("rejected form must not validate submitted credentials")

    monkeypatch.setattr(pages, "validate_registration_fields", forbidden)
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*.db")
    }
    response = client.post("/web/auth/register", data=data)
    assert response.status_code == 403
    assert "请重新打开注册页面" in response.text
    assert "重新打开注册页 →" in response.text
    assert "<form" not in response.text
    assert "set-cookie" not in response.headers
    for value in (
        token,
        "private-name-only",
        "private-only@example.com",
        "private-password-only",
    ):
        assert value not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == digest
        for p, digest in before.items()
    )


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://other.example"},
        {"Origin": "http://testserver:81"},
        {"Origin": "https://testserver"},
        {"Sec-Fetch-Site": "cross-site"},
        {"Origin": "null", "Sec-Fetch-Site": "cross-site"},
    ],
)
def test_cross_site_submission_rejected_even_with_valid_form(client, headers):
    csrf = form_token(client.get("/web/register").text)
    response = client.post(
        "/web/auth/register",
        data={"csrf": csrf, "email": "learner@example.com", "password": PASSWORD},
        headers=headers,
    )
    assert response.status_code == 403
    assert "请重新打开注册页面" in response.text


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": "null"},
        {"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
    ],
)
def test_same_site_and_private_browser_origin_require_and_accept_valid_form(
    client, headers
):
    csrf = form_token(client.get("/web/register").text)
    response = client.post(
        "/web/auth/register",
        data={"csrf": csrf, "email": "learner@example.com", "password": PASSWORD},
        headers=headers,
    )
    assert response.status_code == 200
    assert "无需等待邮件" in response.text
    assert set(client.cookies.keys()) == {pages._COOKIE}


def test_expired_page_can_reopen_and_submit_without_extending_old_context(
    client, monkeypatch
):
    first = form_token(client.get("/web/register").text)
    original = client.cookies.get(pages._COOKIE)
    later = pages.time() + 1800
    monkeypatch.setattr(pages, "time", lambda: later)
    assert client.post("/web/auth/register", data={"csrf": first}).status_code == 403
    reopened = client.get("/web/register")
    assert "set-cookie" in reopened.headers
    new = form_token(reopened.text)
    assert new != first
    assert client.cookies.get(pages._COOKIE) != original
    assert client.post("/web/auth/register", data={"csrf": first}).status_code == 403
    assert (
        client.post(
            "/web/auth/register",
            data={"csrf": new, "email": "learner@example.com", "password": PASSWORD},
        ).status_code
        == 200
    )


def test_multiple_tabs_and_field_error_correction_keep_valid_form(client):
    first = form_token(client.get("/web/register").text)
    assert form_token(client.get("/web/register").text) == first
    error = client.post(
        "/web/auth/register",
        data={
            "csrf": first,
            "name": "称呼",
            "email": "learner@example.com",
            "password": "short-secret",
        },
    )
    assert error.status_code == 400
    assert "register-password-error" in error.text
    assert "short-secret" not in error.text
    assert form_token(error.text) == first
    assert "set-cookie" not in error.headers
    valid = client.post(
        "/web/auth/register",
        data={
            "csrf": first,
            "name": "称呼",
            "email": "learner@example.com",
            "password": PASSWORD,
        },
    )
    assert valid.status_code == 200
    assert "本次尚未发送邮件，也未创建账户" in valid.text


@pytest.mark.parametrize(
    "body",
    [
        "csrf={token}&csrf={token}",
        "csrf={token}&unexpected=1",
        "csrf={token}&name=a&name=b",
        "csrf={token}&email=x&password=x&name=x&extra=x",
    ],
)
def test_duplicate_and_extra_fields_are_rejected_with_valid_cookie(client, body):
    csrf = form_token(client.get("/web/register").text)
    response = client.post(
        "/web/auth/register",
        content=body.format(token=csrf),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 400
    assert "无法读取" in response.text
    assert form_token(response.text) == csrf


@pytest.mark.parametrize(
    "cookie",
    [
        "",
        "bad",
        "x" * 201,
        "a.b.c",
        "a" * 43 + ".abcdefghij." + "b" * 64,
        "a" * 43 + ".%EF%BC%91." + "b" * 64,
        "a" * 43 + ".9999999999." + "b" * 64,
    ],
)
def test_bad_cookie_never_crashes_or_is_accepted_and_get_recovers(client, cookie):
    client.cookies.set(pages._COOKIE, cookie)
    assert client.post("/web/auth/register", data={"csrf": "a" * 43}).status_code == 403
    client.cookies.clear()
    client.cookies.set(pages._COOKIE, cookie)
    reopened = client.get("/web/register")
    assert reopened.status_code == 200
    assert "set-cookie" in reopened.headers
    assert len(form_token(reopened.text)) == 43


def test_restart_requires_new_form_but_writes_nothing(client, tmp_path):
    csrf = form_token(client.get("/web/register").text)
    cookie = client.cookies.get(pages._COOKIE)
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app) as restarted:
        restarted.cookies.set(pages._COOKIE, cookie)
        assert (
            restarted.post("/web/auth/register", data={"csrf": csrf}).status_code == 403
        )
        restarted.cookies.clear()
        assert (
            submit(
                restarted, data={"email": "learner@example.com", "password": PASSWORD}
            ).status_code
            == 200
        )
    repository = SQLiteUserRepository(tmp_path / "users.db")
    assert repository.get_by_email("learner@example.com") is None


def test_https_uses_secure_cookie_and_success_is_not_login(tmp_path):
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app, base_url="https://coach.example.com") as browser:
        page = browser.get("/web/register")
        assert "Secure" in page.headers["set-cookie"]
        assert (
            browser.post(
                "/web/auth/register",
                data={
                    "csrf": form_token(page.text),
                    "email": "learner@example.com",
                    "password": PASSWORD,
                },
                headers={"Origin": "https://coach.example.com"},
            ).status_code
            == 200
        )
        assert set(browser.cookies.keys()) == {pages._COOKIE}


def test_email_confirmation_cookie_cannot_be_renamed_to_registration_form_context(
    client,
):
    page = client.get("/web/verify-registration?token=" + "a" * 43)
    inputs = {
        a["name"]: a.get("value", "")
        for tag, a in Elements(page.text).elements
        if tag == "input"
    }
    original = client.cookies.get("coach_registration_confirmation")
    client.cookies.clear()
    client.cookies.set(pages._COOKIE, original)
    result = client.post(
        "/web/auth/register",
        data={
            "csrf": inputs["csrf"],
            "email": "learner@example.com",
            "password": PASSWORD,
        },
    )
    assert result.status_code == 403
