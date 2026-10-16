import builtins
import os
import socket
import subprocess
import sys
import tempfile
from http.cookiejar import CookieJar
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, ProxyHandler, build_opener

import pytest
from fastapi.testclient import TestClient

from api import mail_test
from security.verification_mailer import MailDeliveryError


SECRET = "test-only-authorization-code"
ADDRESS = "test-only-sender@163.com"


class Inputs(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.values = {}
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.values[attrs["name"]] = attrs["value"]


@pytest.fixture
def harness(monkeypatch):
    import uvicorn

    observed = {"sent": [], "starts": 0, "waits": 0}
    behavior = {}
    server = None
    monkeypatch.setattr(mail_test.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(mail_test.getpass, "getpass", lambda prompt: SECRET)

    def directory(**kwargs):
        handle = tempfile.TemporaryDirectory(**kwargs)
        observed["temporary_directory"] = handle.name
        return handle

    monkeypatch.setattr(
        mail_test, "tempfile", SimpleNamespace(TemporaryDirectory=directory)
    )

    class Socket:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            observed["socket_closed"] = True

        def bind(self, address):
            observed["bound"] = address
            if behavior.get("busy"):
                raise OSError("private socket details")

        def listen(self, backlog):
            pass

    class Server:
        def __init__(self, config):
            nonlocal server
            server = self
            self.config = config
            self.started = False
            self.should_exit = False
            observed["app"] = config.app
            assert config.access_log is False
            assert config.host == "127.0.0.1"

        def run(self, **kwargs):
            observed["starts"] += 1
            self.started = not behavior.get("startup_failed", False)

    class Thread:
        def __init__(self, *, target, kwargs, daemon):
            self.target, self.kwargs = target, kwargs
            assert daemon is True

        def start(self):
            self.target(**self.kwargs)

        def is_alive(self):
            return server.started and not server.should_exit

        def join(self, timeout):
            if server.should_exit:
                observed["shutdown"] = True
                return
            if timeout != 0.5:
                return
            observed["waits"] += 1
            if behavior.get("interrupt"):
                raise KeyboardInterrupt
            message = observed["sent"][0]
            with TestClient(
                observed["app"], base_url="http://127.0.0.1:8774"
            ) as client:
                page = client.get(message.activation_url)
                assert "确认这是你的邮箱" in page.text
                result = client.post(
                    "/web/verify-email",
                    data=Inputs(page.text).values,
                    headers={"Origin": "null"},
                )
                assert "邮箱验证成功" in result.text
                assert result.status_code == 200
                observed["browser_verified"] = True

    def send(message, settings):
        assert server.started
        assert message.recipient == settings.username == ADDRESS
        assert settings.authorization_code == SECRET
        observed["sent"].append(message)
        if "delivery_error" in behavior:
            raise MailDeliveryError(behavior["delivery_error"], "模拟投递状态")

    monkeypatch.setattr(
        mail_test,
        "socket",
        SimpleNamespace(
            socket=Socket, AF_INET=socket.AF_INET, SOCK_STREAM=socket.SOCK_STREAM
        ),
    )
    monkeypatch.setattr(mail_test, "threading", SimpleNamespace(Thread=Thread))
    monkeypatch.setattr(uvicorn, "Server", Server)
    monkeypatch.setattr(mail_test, "send_verification_email", send)
    return observed, behavior


def answers(monkeypatch, *values):
    iterator = iter(values)
    monkeypatch.setattr(builtins, "input", lambda prompt: next(iterator))


def test_one_self_addressed_mail_to_browser_confirmation_and_cleanup(
    harness, monkeypatch, capsys
):
    observed, _ = harness
    answers(monkeypatch, ADDRESS, "发送")
    assert mail_test.main([]) == 0
    assert len(observed["sent"]) == 1
    assert observed["bound"] == ("127.0.0.1", 8774)
    assert observed["browser_verified"]
    assert observed["shutdown"] and observed["socket_closed"]
    assert not Path(observed["temporary_directory"]).exists()
    output = capsys.readouterr()
    assert "测试通过" in output.out
    assert SECRET not in output.out + output.err
    assert observed["sent"][0].activation_url not in output.out + output.err


@pytest.mark.parametrize("reply", ["", "取消", "send"])
def test_cancel_never_starts_service_or_sends(harness, monkeypatch, reply):
    observed, _ = harness
    answers(monkeypatch, ADDRESS, reply)
    assert mail_test.main([]) == 0
    assert observed["starts"] == 0
    assert observed["sent"] == []


def test_noninteractive_input_is_refused_before_password_or_send(harness, monkeypatch):
    observed, _ = harness
    monkeypatch.setattr(mail_test.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    answers(monkeypatch)
    assert mail_test.main([]) == 1
    assert observed["sent"] == []


def test_non_hidden_password_fallback_stops(harness, monkeypatch, capsys):
    observed, _ = harness
    answers(monkeypatch, ADDRESS)

    def unsafe_prompt(prompt):
        import warnings

        warnings.warn("test-only-warning", mail_test.getpass.GetPassWarning)

    monkeypatch.setattr(mail_test.getpass, "getpass", unsafe_prompt)
    assert mail_test.main([]) == 1
    assert observed["sent"] == []
    assert "不能隐藏" in capsys.readouterr().out


@pytest.mark.parametrize(
    "address", ["other@example.com", "bad", "a@163.com\nBcc:other@example.com"]
)
def test_invalid_sender_never_starts_or_sends(harness, monkeypatch, address):
    observed, _ = harness
    answers(monkeypatch, address)
    assert mail_test.main([]) == 1
    assert not observed["starts"]
    assert not observed["sent"]


@pytest.mark.parametrize("code", ["timeout", "connection_failed"])
def test_uncertain_delivery_keeps_page_usable_and_never_resends(
    harness, monkeypatch, code
):
    observed, behavior = harness
    behavior["delivery_error"] = code
    answers(monkeypatch, ADDRESS, "发送")
    assert mail_test.main([]) == 0
    assert len(observed["sent"]) == 1
    assert observed["browser_verified"]


def test_authentication_failure_stops_without_retry(harness, monkeypatch):
    observed, behavior = harness
    behavior["delivery_error"] = "authentication_failed"
    answers(monkeypatch, ADDRESS, "发送")
    assert mail_test.main([]) == 1
    assert len(observed["sent"]) == 1
    assert observed["waits"] == 0
    assert observed["shutdown"]


@pytest.mark.parametrize("failure", ["busy", "startup_failed"])
def test_no_mail_is_sent_unless_local_page_is_ready(harness, monkeypatch, failure):
    observed, behavior = harness
    behavior[failure] = True
    answers(monkeypatch, ADDRESS, "发送")
    assert mail_test.main([]) == 1
    assert observed["sent"] == []
    assert observed["socket_closed"]


def test_interruption_after_send_closes_server_without_retry(harness, monkeypatch):
    observed, behavior = harness
    behavior["interrupt"] = True
    answers(monkeypatch, ADDRESS, "发送")
    assert mail_test.main([]) == 130
    assert observed["shutdown"] and observed["socket_closed"]
    assert len(observed["sent"]) == 1


def test_help_does_not_need_terminal_or_credentials(monkeypatch, capsys):
    monkeypatch.setattr(mail_test.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    with pytest.raises(SystemExit) as caught:
        mail_test.main(["--help"])
    assert caught.value.code == 0
    assert "--port" in capsys.readouterr().out


def test_test_pages_have_valid_read_only_navigation(tmp_path):
    from user.sqlite_repository import SQLiteUserRepository

    app = mail_test._create_test_app(SQLiteUserRepository(tmp_path / "users.db"))
    with TestClient(app) as client:
        for path in ["/", "/web/login", "/web/register", "/static/public.css"]:
            assert client.get(path).status_code == 200
        assert (
            client.post(
                "/web/register", data={"name": "test", "email": ADDRESS}
            ).status_code
            == 405
        )


@pytest.mark.integration
def test_real_loopback_server_with_simulated_mail_round_trip(monkeypatch, capsys):
    submitted = []

    def simulated_mail(message, settings):
        submitted.append(message)
        opener = build_opener(ProxyHandler({}), HTTPCookieProcessor(CookieJar()))
        with opener.open(message.activation_url, timeout=5) as page:
            form = Inputs(page.read().decode("utf-8")).values
        destination = message.activation_url.split("?", 1)[0]
        with opener.open(
            destination, data=urlencode(form).encode("ascii"), timeout=5
        ) as result:
            assert result.status == 200
            assert "邮箱验证成功" in result.read().decode("utf-8")

    monkeypatch.setattr(mail_test, "send_verification_email", simulated_mail)
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    settings = mail_test.SMTPSettings(ADDRESS, SECRET)
    assert mail_test._run_test(settings, port) == 0
    assert len(submitted) == 1
    output = capsys.readouterr()
    assert "测试通过" in output.out
    assert SECRET not in output.out + output.err
    assert submitted[0].activation_url not in output.out + output.err


def test_mail_test_app_is_independent_of_ai_configuration(tmp_path):
    source = Path(__file__).resolve().parents[1]
    env = dict(
        os.environ,
        PYTHONPATH=str(source),
        DEEPSEEK_API_KEY="",
        LLM_TIMEOUT="invalid",
        PYTHONDONTWRITEBYTECODE="1",
    )
    code = (
        "import sys; from pathlib import Path; "
        "from api.mail_test import _create_test_app; "
        "from user.sqlite_repository import SQLiteUserRepository; "
        "_create_test_app(SQLiteUserRepository(Path(sys.argv[1])/'users.db')); "
        "assert 'config' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-B", "-c", code, str(tmp_path)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
