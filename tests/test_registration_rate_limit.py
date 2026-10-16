import hashlib
import smtplib
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from api import registration_pages as pages
from api.app import create_app
from security.registration_rate_limit import RegistrationRateLimiter


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.values[attrs["name"]] = attrs.get("value", "")


def test_rolling_boundary_and_rejections_do_not_extend_wait():
    clock = Clock()
    limiter = RegistrationRateLimiter(per_client_limit=2, total_limit=10, clock=clock)
    assert limiter.admit("a") == 0
    clock.now += 10
    assert limiter.admit("a") == 0
    assert limiter.admit("a") == 50
    clock.now = 1059.01
    assert limiter.admit("a") == 1
    clock.now = 1060
    assert limiter.admit("a") == 0
    assert limiter.admit("a") == 10
    clock.now = 1070
    assert limiter.admit("a") == 0


def test_global_budget_is_shared_and_retry_covers_both_limits():
    clock = Clock()
    limiter = RegistrationRateLimiter(per_client_limit=1, total_limit=2, clock=clock)
    assert limiter.admit("a") == 0
    clock.now += 10
    assert limiter.admit("b") == 0
    assert limiter.admit("c") == 50
    assert limiter.admit("b") == 60
    clock.now += 50
    assert limiter.admit("b") == 10
    assert limiter.admit("c") == 0


def test_memory_is_bounded_and_inactive_clients_are_removed():
    clock = Clock()
    limiter = RegistrationRateLimiter(per_client_limit=2, total_limit=20, clock=clock)
    results = [limiter.admit(f"peer-{i}") for i in range(200)]
    assert results.count(0) == 20
    assert len(limiter._clients) == len(limiter._total) == 20
    clock.now += 60
    assert limiter.admit("new") == 0
    assert set(limiter._clients) == {"new"}
    assert len(limiter._total) == 1


@pytest.mark.parametrize("shared_peer,limit", [(True, 10), (False, 12)])
def test_concurrent_admission_never_exceeds_either_budget(shared_peer, limit):
    limiter = RegistrationRateLimiter(
        per_client_limit=10, total_limit=12, clock=Clock()
    )
    barrier = Barrier(24)

    def attempt(index):
        barrier.wait(timeout=10)
        return limiter.admit("shared" if shared_peer else str(index))

    with ThreadPoolExecutor(max_workers=24) as executor:
        results = list(executor.map(attempt, range(24)))
    assert results.count(0) == limit
    assert set(results) == {0, 60}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    clock = Clock()

    def factory(**kwargs):
        return RegistrationRateLimiter(**kwargs, clock=clock)

    def no_mail(*args, **kwargs):
        raise AssertionError("rate limit tests must never contact SMTP")

    monkeypatch.setattr(pages, "RegistrationRateLimiter", factory)
    monkeypatch.setattr(smtplib, "SMTP", no_mail)
    monkeypatch.setattr(smtplib, "SMTP_SSL", no_mail)
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app, client=("192.0.2.1", 50000)) as client:
        yield app, client, clock, tmp_path


def token(client):
    page = client.get("/web/register")
    assert page.status_code == 200
    return Inputs(page.text).values["csrf"]


def data(csrf):
    return {
        "csrf": csrf,
        "email": "private-test@example.com",
        "password": "private-test-only phrase",
    }


def test_default_post_limit_has_private_response_and_recovers_exactly(setup):
    _, client, clock, directory = setup
    csrf = token(client)
    before = {
        p: hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.rglob("*.db")
    }
    for _ in range(10):
        assert client.post("/web/auth/register", data=data(csrf)).status_code == 200
    blocked = client.post("/web/auth/register", data=data(csrf))
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
    assert "请在 60 秒后" in blocked.text
    assert "操作有些频繁，请稍等一下" in blocked.text
    assert "<form" not in blocked.text
    for value in (csrf, "private-test@example.com", "private-test-only phrase"):
        assert value not in blocked.text
    for header, value in (
        ("cache-control", "no-store"),
        ("referrer-policy", "no-referrer"),
        ("x-frame-options", "DENY"),
    ):
        assert blocked.headers[header] == value
    assert "set-cookie" not in blocked.headers
    clock.now += 59.2
    assert (
        client.post("/web/auth/register", data=data(csrf)).headers["retry-after"] == "1"
    )
    clock.now += 0.8
    assert client.post("/web/auth/register", data=data(csrf)).status_code == 200
    assert all(
        hashlib.sha256(p.read_bytes()).hexdigest() == digest
        for p, digest in before.items()
    )


def test_get_limit_is_independent_preserves_context_and_keeps_other_pages_usable(setup):
    _, client, clock, _ = setup
    csrf = token(client)
    cookie = client.cookies.get(pages._COOKIE)
    for _ in range(29):
        assert client.get("/web/register").status_code == 200
    blocked = client.get("/web/register")
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
    assert "set-cookie" not in blocked.headers
    assert client.cookies.get(pages._COOKIE) == cookie
    assert client.post("/web/auth/register", data=data(csrf)).status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/web/login").status_code == 200
    assert client.get("/static/public.css").status_code == 200
    clock.now += 60
    assert token(client) == csrf


def test_post_limit_does_not_block_reopening_form_or_email_confirmation(setup):
    _, client, _, _ = setup
    for _ in range(10):
        assert client.post("/web/auth/register", data={}).status_code == 403
    assert client.post("/web/auth/register", data={}).status_code == 429
    assert token(client)
    assert client.get("/web/verify-email?token=" + "a" * 43).status_code == 200
    assert client.get("/web/verify-registration?token=" + "a" * 43).status_code == 200


def test_cookies_forwarded_headers_and_source_port_cannot_reset_peer_limit(setup):
    app, client, _, _ = setup
    for _ in range(10):
        assert client.post("/web/auth/register", data={}).status_code == 403
    client.cookies.clear()
    response = client.post(
        "/web/auth/register",
        headers={
            "X-Forwarded-For": "198.51.100.9",
            "Forwarded": "for=198.51.100.10",
            "X-Real-IP": "198.51.100.11",
        },
    )
    assert response.status_code == 429
    with TestClient(app, client=("192.0.2.1", 59999)) as other_port:
        assert other_port.post("/web/auth/register").status_code == 429
    with TestClient(app, client=("192.0.2.2", 50000)) as other_peer:
        assert other_peer.post("/web/auth/register").status_code == 403


@pytest.mark.parametrize("method,total", [("get", 240), ("post", 120)])
def test_global_default_budget_stops_many_sources_and_recovers(setup, method, total):
    app, _, clock, _ = setup
    path = "/web/register" if method == "get" else "/web/auth/register"
    expected = 200 if method == "get" else 403
    for index in range(total):
        with TestClient(app, client=(f"peer-{index}", 50000)) as peer:
            assert peer.request(method.upper(), path).status_code == expected
    with TestClient(app, client=("new-peer", 50000)) as peer:
        assert peer.request(method.upper(), path).status_code == 429
        clock.now += 60
        assert peer.request(method.upper(), path).status_code == expected


@pytest.mark.parametrize("kind", ["bad-csrf", "cross-site", "json", "oversized"])
def test_invalid_attempts_are_limited_before_field_validation(setup, monkeypatch, kind):
    _, client, _, _ = setup
    csrf = token(client)

    def forbidden(*args, **kwargs):
        raise AssertionError("invalid or limited request must not validate credentials")

    monkeypatch.setattr(pages, "validate_registration_fields", forbidden)
    kwargs, expected = {"data": {"csrf": "a" * 43}}, 403
    if kind == "cross-site":
        kwargs = {"data": data(csrf), "headers": {"Origin": "https://other.example"}}
    elif kind == "json":
        kwargs, expected = {"json": {"password": "private-test-only"}}, 400
    elif kind == "oversized":
        kwargs, expected = (
            {
                "content": "password=" + "x" * 9000,
                "headers": {"Content-Type": "application/x-www-form-urlencoded"},
            },
            400,
        )
    for _ in range(10):
        assert client.post("/web/auth/register", **kwargs).status_code == expected
    response = client.post("/web/auth/register", **kwargs)
    assert response.status_code == 429
    assert "private-test-only" not in response.text


def test_unknown_transport_peer_has_shared_conservative_budget(setup):
    app, _, _, _ = setup
    with TestClient(app, client=None) as unknown:
        for _ in range(10):
            assert unknown.post("/web/auth/register").status_code == 403
        assert unknown.post("/web/auth/register").status_code == 429


def test_limits_are_per_app_instance_without_persistent_state(setup):
    _, client, _, directory = setup
    for _ in range(10):
        client.post("/web/auth/register")
    assert client.post("/web/auth/register").status_code == 429
    restarted = create_app(
        directory,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(restarted, client=("192.0.2.1", 50000)) as other:
        assert other.post("/web/auth/register").status_code == 403
