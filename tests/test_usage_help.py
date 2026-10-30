import smtplib

import pytest
import requests
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from api.coach_run import build_app, main
from security.verification_mailer import SMTPSettings


@pytest.fixture(autouse=True)
def no_providers(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("usage help cannot call providers")

    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


@pytest.mark.parametrize("simulated, expected", [(False, 8785), (True, 8784)])
def test_check_uses_same_default_port_as_start(
    monkeypatch, tmp_path, simulated, expected
):
    from api import coach_run

    calls = []
    monkeypatch.setattr(
        coach_run, "check_ready", lambda *a, **k: calls.append((a, k)) or 0
    )
    argv = ["--check", "--data-dir", str(tmp_path)] + (
        ["--simulate"] if simulated else []
    )
    assert main(argv) == 0
    assert calls[0][0] == (tmp_path.resolve(), expected)
    assert calls[0][1]["simulated"] is simulated


@pytest.mark.parametrize("flags", [[], ["--simulate"]])
def test_explicit_port_and_directory_still_work(monkeypatch, tmp_path, flags):
    from api import coach_run

    calls = []
    monkeypatch.setattr(coach_run, "_serve", lambda *a, **k: calls.append(a) or 0)
    assert main([*flags, "--port", "9891", "--data-dir", str(tmp_path)]) == 0
    assert calls == [(tmp_path.resolve(), 9891)]


def test_help_is_app_local_not_inferred_from_port_and_does_not_write_data(tmp_path):
    local_dir, sim_dir, preview_dir = (
        tmp_path / name for name in ("local", "sim", "preview")
    )
    for directory in (local_dir, sim_dir, preview_dir):
        directory.mkdir()
    # Deliberately reverse conventional ports: the explicit mode must win.
    local = build_app(local_dir, 8784)
    simulated = build_app(sim_dir, 8785, simulated=True)
    preview = create_account_app(preview_dir)
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with (
        TestClient(local) as real,
        TestClient(simulated) as fake,
        TestClient(preview) as dev,
    ):
        for _ in range(2):
            response = real.get("/web/help")
            assert "当前环境 · 本机日常使用" in response.text
            assert "未启用 · 可查阅已有记录" in response.text
            assert "未启用 · 已验证账户仍可登录" in response.text
            assert "当前环境 · 模拟体验" in fake.get("/web/help").text
            assert "当前环境 · 开发预览" in dev.get("/web/help").text
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "set-cookie" not in response.headers
        assert "遇到问题，先这样做" in response.text
        assert 'href="/web/forgot-password"' in response.text
        assert "系统不会自动重试" in response.text
        assert str(tmp_path) not in response.text
        assert "使用帮助与当前环境" in real.get("/web/login").text
        assert real.get("/web/trial-mailbox").status_code == 404
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


def test_help_reports_explicit_ai_and_mail_without_disclosing_configuration(tmp_path):
    settings = SMTPSettings("private-sender@163.com", "private-authorization-value")
    app = build_app(
        tmp_path, 9891, settings=settings, responder=lambda *a: pytest.fail("no AI")
    )
    with TestClient(app, base_url="http://untrusted-host.example") as client:
        response = client.get("/web/help")
    assert response.status_code == 200
    assert "已启用 · 主动发送或生成时可能计费" in response.text
    assert "已启用 · 仅限本次配置的本人邮箱" in response.text
    for private in (
        settings.username,
        "private-authorization-value",
        "untrusted-host.example",
        str(tmp_path),
    ):
        assert private not in response.text


def test_legacy_entry_has_help_without_linking_to_unavailable_workspace(tmp_path):
    from api.app import create_app

    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app) as client:
        response = client.get("/web/help")
    assert "当前环境 · 旧开发入口" in response.text
    assert 'href="/web/welcome"' not in response.text
    assert 'href="/web/forgot-password"' not in response.text


def test_old_mail_test_footer_help_is_available_without_sending(tmp_path):
    from api.mail_test import _create_test_app
    from user.sqlite_repository import SQLiteUserRepository

    repository = SQLiteUserRepository(tmp_path / "users.db")
    app = _create_test_app(repository)
    before = (tmp_path / "users.db").read_bytes()
    with TestClient(app) as client:
        assert 'href="/web/help"' in client.get("/").text
        response = client.get("/web/help")
        assert response.status_code == 200
        assert "当前环境 · 旧开发入口" in response.text
        assert 'href="/web/welcome"' not in response.text
    assert (tmp_path / "users.db").read_bytes() == before
