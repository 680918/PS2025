import builtins
import getpass
import smtplib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient

from api import account_test
from security.verification_mailer import SMTPSettings


PASSWORD = "a temporary trial account phrase"


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.fields = {}
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.fields[attrs["name"]] = attrs.get("value", "")
        if tag == "a":
            self.links.append(attrs.get("href", ""))


@pytest.fixture(autouse=True)
def no_real_mail(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append(True)
        raise AssertionError("no real SMTP")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    yield
    assert calls == []


def register_and_send(client, email):
    csrf = Page(client.get("/web/register").text).fields["csrf"]
    saved = client.post(
        "/web/auth/register",
        data={"csrf": csrf, "email": email, "name": "试用者", "password": PASSWORD},
    )
    return client.post("/web/register/send-verification", data=Page(saved.text).fields)


def test_simulated_trial_runs_complete_account_flow_and_mailbox_is_owner_bound(
    tmp_path,
):
    app = account_test.create_trial_app(tmp_path, simulated=True)
    with TestClient(app, base_url="http://127.0.0.1:8782") as client:
        assert register_and_send(client, "demo@example.com").status_code == 200
        mailbox = client.get("/web/trial-mailbox")
        link = next(link for link in Page(mailbox.text).links if "?token=" in link)
        with TestClient(app, base_url="http://127.0.0.1:8782") as outsider:
            assert "?token=" not in outsider.get("/web/trial-mailbox").text
        confirmation = client.get(link)
        assert (
            client.post(
                "/web/verify-registration", data=Page(confirmation.text).fields
            ).status_code
            == 200
        )
        assert not account_test._completed(tmp_path)
        csrf = Page(client.get("/web/login").text).fields["csrf"]
        logged_in = client.post(
            "/web/auth/login",
            data={"csrf": csrf, "email": "demo@example.com", "password": PASSWORD},
        )
        assert "欢迎回来，试用者。" in logged_in.text
        assert not account_test._completed(tmp_path)
        client.post("/web/auth/logout", data=Page(logged_in.text).fields)
        assert account_test._completed(tmp_path)


def test_real_trial_restricts_recipient_before_smtp_and_has_no_fake_mailbox(
    tmp_path, monkeypatch
):
    import security.registration_delivery as delivery

    sent = []
    monkeypatch.setattr(
        delivery,
        "send_verification_email",
        lambda message, settings, **kwargs: sent.append(message),
    )
    settings = SMTPSettings("self-only@163.com", "fake-code")
    app = account_test.create_trial_app(tmp_path, settings=settings)
    with TestClient(app, base_url="http://127.0.0.1:8782") as client:
        assert client.get("/web/trial-mailbox").status_code == 404
        result = register_and_send(client, "someone-else@example.com")
        assert "邮件暂未发出" in result.text
        assert sent == []
    with TestClient(app, base_url="http://127.0.0.1:8782") as self_client:
        assert register_and_send(self_client, settings.username).status_code == 200
    assert len(sent) == 1
    assert sent[0].recipient == settings.username


def test_simulated_links_use_configured_port(tmp_path):
    app = account_test.create_trial_app(
        tmp_path,
        simulated=True,
        activation_url="http://127.0.0.1:9891/web/verify-registration",
    )
    with TestClient(app, base_url="http://127.0.0.1:9891") as client:
        register_and_send(client, "demo@example.com")
        assert (
            "127.0.0.1:9891/web/verify-registration?token="
            in client.get("/web/trial-mailbox").text
        )


def test_noninteractive_real_trial_rejects_before_prompt_or_server(monkeypatch, capsys):
    monkeypatch.setattr(
        account_test.sys, "stdin", SimpleNamespace(isatty=lambda: False)
    )
    monkeypatch.setattr(
        account_test, "_run_trial", lambda *a, **k: pytest.fail("must not start")
    )
    assert account_test.main([]) == 1
    assert "不要通过聊天" in capsys.readouterr().out


def test_real_trial_cancel_does_not_start_or_echo_authorization(monkeypatch, capsys):
    monkeypatch.setattr(account_test.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    inputs = iter(["self-only@163.com", "取消"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(inputs))
    monkeypatch.setattr(
        account_test.getpass, "getpass", lambda prompt: "private-authorization-code"
    )
    monkeypatch.setattr(
        account_test, "_run_trial", lambda *a, **k: pytest.fail("must not start")
    )
    assert account_test.main([]) == 0
    output = capsys.readouterr().out
    assert "已取消" in output
    assert "private-authorization-code" not in output


def test_getpass_warning_stops_without_echo_or_server(monkeypatch):
    monkeypatch.setattr(account_test.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(builtins, "input", lambda prompt: "self-only@163.com")

    def warning(prompt):
        raise getpass.GetPassWarning("cannot hide")

    monkeypatch.setattr(account_test.getpass, "getpass", warning)
    monkeypatch.setattr(
        account_test, "_run_trial", lambda *a, **k: pytest.fail("must not start")
    )
    assert account_test.main([]) == 1


def test_simulation_never_prompts_for_email_credentials(monkeypatch):
    observed = []
    monkeypatch.setattr(
        builtins, "input", lambda prompt: pytest.fail("must not prompt")
    )
    monkeypatch.setattr(
        account_test.getpass, "getpass", lambda prompt: pytest.fail("must not prompt")
    )
    monkeypatch.setattr(
        account_test,
        "_run_trial",
        lambda port, **kwargs: observed.append((port, kwargs)) or 0,
    )
    assert account_test.main(["--simulate", "--port", "9891"]) == 0
    assert observed == [(9891, {"simulated": True})]


def test_real_trial_requires_explicit_start_and_only_passes_transient_settings(
    monkeypatch,
):
    observed = []
    monkeypatch.setattr(account_test.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    inputs = iter(["self-only@163.com", "开始"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(inputs))
    monkeypatch.setattr(
        account_test.getpass, "getpass", lambda prompt: "private-test-code"
    )
    monkeypatch.setattr(
        account_test, "_run_trial", lambda port, **kwargs: observed.append(kwargs) or 0
    )
    assert account_test.main([]) == 0
    assert observed[0]["settings"].username == "self-only@163.com"
    assert "private-test-code" not in repr(observed)


def test_runner_reserves_port_uses_loopback_and_cleans_temporary_data(
    monkeypatch, capsys
):
    import uvicorn

    seen = {}

    class Socket:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            seen["closed"] = True

        def bind(self, address):
            seen["bound"] = address

        def listen(self, backlog):
            pass

    class Server:
        def __init__(self, config):
            self.config = config
            assert config.host == "127.0.0.1"
            assert config.access_log is False and config.proxy_headers is False

        def run(self, **kwargs):
            with TestClient(
                self.config.app, base_url="http://127.0.0.1:9891"
            ) as client:
                register_and_send(client, "demo@example.com")
                link = next(
                    link
                    for link in Page(client.get("/web/trial-mailbox").text).links
                    if "?token=" in link
                )
                client.post(
                    "/web/verify-registration", data=Page(client.get(link).text).fields
                )
                csrf = Page(client.get("/web/login").text).fields["csrf"]
                client.post(
                    "/web/auth/login",
                    data={
                        "csrf": csrf,
                        "email": "demo@example.com",
                        "password": PASSWORD,
                    },
                )
                client.post(
                    "/web/auth/logout",
                    data=Page(client.get("/web/welcome").text).fields,
                )

    original = account_test.create_trial_app

    def capture(directory, **kwargs):
        seen["directory"] = directory
        return original(directory, **kwargs)

    monkeypatch.setattr(account_test, "create_trial_app", capture)
    monkeypatch.setattr(
        account_test,
        "socket",
        SimpleNamespace(
            AF_INET=account_test.socket.AF_INET,
            SOCK_STREAM=account_test.socket.SOCK_STREAM,
            socket=Socket,
        ),
    )
    monkeypatch.setattr(uvicorn, "Server", Server)
    assert account_test._run_trial(9891, simulated=True) == 0
    assert seen["bound"] == ("127.0.0.1", 9891) and seen["closed"]
    assert not Path(seen["directory"]).exists()
    assert "测试通过" in capsys.readouterr().out


def test_busy_port_stops_before_creating_app_or_sending(monkeypatch):
    class BusySocket:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bind(self, address):
            raise OSError("busy")

    monkeypatch.setattr(
        account_test,
        "socket",
        SimpleNamespace(AF_INET=2, SOCK_STREAM=1, socket=BusySocket),
    )
    monkeypatch.setattr(
        account_test, "create_trial_app", lambda *a, **k: pytest.fail("must not build")
    )
    with pytest.raises(OSError):
        account_test._run_trial(9891, simulated=True)


def test_account_app_import_does_not_load_ai_or_environment_config(tmp_path):
    code = "import sys;from pathlib import Path;from api.account_app import create_account_app;create_account_app(Path(sys.argv[1]));assert 'config' not in sys.modules;assert 'agent.controller' not in sys.modules;print('isolated-account-app-ok')"
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert "isolated-account-app-ok" in result.stdout
