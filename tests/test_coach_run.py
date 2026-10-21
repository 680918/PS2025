import builtins
import smtplib
from types import SimpleNamespace

import pytest
import requests
from fastapi.testclient import TestClient

from api import coach_run
from tests.test_web_coach_dialogue import Forms, PASSWORD, add_user, form, login
from security.passwords import hash_password


@pytest.fixture(autouse=True)
def no_external_services(monkeypatch):
    def forbidden(*a, **k):
        pytest.fail("no real services in runner tests")

    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)


def test_default_start_never_loads_ai_or_prompts_and_uses_persistent_directory(
    monkeypatch,
):
    seen = []
    monkeypatch.setattr(builtins, "input", lambda *a: pytest.fail("no prompt"))
    monkeypatch.setattr(coach_run, "_serve", lambda *a, **k: seen.append((a, k)) or 0)
    assert coach_run.main([]) == 0
    args, kwargs = seen[0]
    assert args[0] == coach_run.ROOT / "data/coach-local"
    assert args[1] == 8785
    assert kwargs == {"simulated": False, "settings": None, "responder": None}


def test_simulation_has_independent_directory_and_never_requests_real_ai(monkeypatch):
    from coach import dialogue

    seen = []
    monkeypatch.setattr(dialogue, "real_responder", lambda: pytest.fail("no real AI"))
    monkeypatch.setattr(coach_run, "_serve", lambda *a, **k: seen.append((a, k)) or 0)
    assert coach_run.main(["--simulate"]) == 0
    assert seen[0][0][0] == coach_run.ROOT / "data/coach-simulated"
    assert seen[0][0][1] == 8784
    assert callable(seen[0][1]["responder"])


def test_real_ai_requires_explicit_flag_and_validates_before_server(
    monkeypatch, tmp_path
):
    from coach import dialogue

    seen = []

    def responder(*args):
        return None

    monkeypatch.setattr(dialogue, "real_responder", lambda: responder)
    monkeypatch.setattr(coach_run, "_serve", lambda *a, **k: seen.append(k) or 0)
    assert coach_run.main(["--ai", "--data-dir", str(tmp_path)]) == 0
    assert seen[0]["responder"] is responder

    def invalid():
        raise ValueError("private configuration")

    monkeypatch.setattr(dialogue, "real_responder", invalid)
    assert coach_run.main(["--ai"]) == 1
    assert len(seen) == 1


@pytest.mark.parametrize("flag", ["--ai", "--register"])
def test_simulation_rejects_mixed_modes(flag):
    with pytest.raises(SystemExit):
        coach_run.main(["--simulate", flag])


def test_registration_requires_hidden_interactive_input_and_does_not_echo_secret(
    monkeypatch, capsys
):
    seen = []
    monkeypatch.setattr(coach_run.sys, "stdin", SimpleNamespace(isatty=lambda: False))
    assert coach_run.main(["--register"]) == 1
    monkeypatch.setattr(coach_run.sys, "stdin", SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(builtins, "input", lambda *a: "self@163.com")
    monkeypatch.setattr(
        coach_run.getpass, "getpass", lambda *a: "private-authorization"
    )
    monkeypatch.setattr(coach_run, "_serve", lambda *a, **k: seen.append(k) or 0)
    assert coach_run.main(["--register"]) == 0
    assert seen[0]["settings"].username == "self@163.com"
    assert "private-authorization" not in capsys.readouterr().out + repr(seen)


def test_persistent_app_restores_dialogue_after_restart_without_smtp_configuration(
    tmp_path,
):
    add_user(tmp_path, hash_password(PASSWORD), "one@example.com", "持续学习者")
    app = coach_run.build_app(tmp_path, 8784, simulated=True)
    with TestClient(app, base_url="https://coach.example.com") as client:
        login(client)
        first = client.post("/web/coach/message", data=form(client))
        assert "模拟回复" in first.text and "时间管理" in first.text
        client.post(
            "/web/auth/logout", data=Forms(first.text).values("/web/auth/logout")
        )
    restarted = coach_run.build_app(tmp_path, 8784)
    with TestClient(restarted, base_url="https://coach.example.com") as fresh:
        page = login(fresh)
        assert "时间管理" in page.text and "AI 对话未启用" in page.text
        assert fresh.get("/web/trial-mailbox").status_code == 404


def test_server_is_loopback_and_keeps_data_on_stop_and_refuses_mode_mix(
    monkeypatch, tmp_path
):
    import uvicorn

    seen = {}

    class Listener:
        def __init__(self, *a):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            seen["closed"] = True

        def bind(self, address):
            seen["bound"] = address

        def listen(self, *a):
            pass

    class Server:
        def __init__(self, config):
            assert config.host == "127.0.0.1"
            assert not config.access_log and not config.proxy_headers

        def run(self, **kwargs):
            seen["ran"] = True

    monkeypatch.setattr(
        coach_run, "socket", SimpleNamespace(socket=Listener, AF_INET=2, SOCK_STREAM=1)
    )
    monkeypatch.setattr(uvicorn, "Server", Server)
    assert coach_run._serve(tmp_path, 9891, simulated=True) == 0
    assert seen["bound"] == ("127.0.0.1", 9891) and seen["closed"] and seen["ran"]
    assert (tmp_path / "users.db").exists()
    assert (tmp_path / "coach_conversations.db").exists()
    with pytest.raises(ValueError):
        coach_run._serve(tmp_path, 9891)
    assert (tmp_path / ".coach-mode").read_text(encoding="utf-8") == "simulated"


def test_busy_port_prevents_app_creation_and_any_data_write(monkeypatch, tmp_path):
    class Busy:
        def __init__(self, *a):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def bind(self, *a):
            raise OSError("busy")

    monkeypatch.setattr(
        coach_run, "socket", SimpleNamespace(socket=Busy, AF_INET=2, SOCK_STREAM=1)
    )
    directory = tmp_path / "not-created"
    with pytest.raises(OSError):
        coach_run._serve(directory, 9891)
    assert not directory.exists()


def test_real_responder_configuration_is_lazy_and_bounded(monkeypatch):
    import sys
    from coach.dialogue import real_responder

    calls = []
    monkeypatch.setitem(
        sys.modules,
        "config",
        SimpleNamespace(DEEPSEEK_API_KEY="fake-key", LLM_TIMEOUT=30),
    )
    monkeypatch.setitem(
        sys.modules,
        "llm_client",
        SimpleNamespace(call_llm=lambda *a: calls.append(True)),
    )
    assert callable(real_responder()) and calls == []
    monkeypatch.setitem(
        sys.modules, "config", SimpleNamespace(DEEPSEEK_API_KEY="", LLM_TIMEOUT=30)
    )
    with pytest.raises(ValueError):
        real_responder()
    monkeypatch.setitem(
        sys.modules,
        "config",
        SimpleNamespace(DEEPSEEK_API_KEY="fake-key", LLM_TIMEOUT=181),
    )
    with pytest.raises(ValueError):
        real_responder()
