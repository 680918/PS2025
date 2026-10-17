import builtins
import smtplib
import sys
from types import SimpleNamespace

import pytest
import requests

from api import coach_run


@pytest.fixture(autouse=True)
def isolated_checks(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("preflight must not prompt, serve, or contact external services")

    monkeypatch.setattr(builtins, "input", forbidden)
    monkeypatch.setattr(coach_run.getpass, "getpass", forbidden)
    monkeypatch.setattr(coach_run, "_serve", forbidden)
    monkeypatch.setattr(coach_run, "build_app", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)
    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)

    class Listener:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bind(self, address):
            assert address == ("127.0.0.1", 9891)

    monkeypatch.setattr(
        coach_run, "socket", SimpleNamespace(socket=Listener, AF_INET=2, SOCK_STREAM=1)
    )


@pytest.mark.parametrize("mode", [[], ["--simulate"], ["--register"]])
def test_offline_check_does_not_load_ai_create_data_or_prompt(
    mode, monkeypatch, tmp_path, capsys
):
    from coach import dialogue

    monkeypatch.setattr(
        dialogue, "real_responder", lambda: pytest.fail("AI not explicitly selected")
    )
    original_import = coach_run.importlib.import_module

    def import_without_config(name):
        assert name not in ("config", "llm_client")
        return original_import(name)

    monkeypatch.setattr(coach_run.importlib, "import_module", import_without_config)
    directory = tmp_path / "not-created"
    assert (
        coach_run.main(
            ["--check", "--port", "9891", "--data-dir", str(directory), *mode]
        )
        == 0
    )
    assert not directory.exists()
    output = capsys.readouterr().out
    assert "不调用 AI" in output and "检查通过" in output


def test_ai_check_builds_responder_but_never_invokes_it_or_exposes_secrets(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setitem(
        sys.modules,
        "config",
        SimpleNamespace(DEEPSEEK_API_KEY="private-test-key", LLM_TIMEOUT=30),
    )
    monkeypatch.setitem(
        sys.modules,
        "llm_client",
        SimpleNamespace(call_llm=lambda *a: pytest.fail("no AI request")),
    )
    assert (
        coach_run.main(
            [
                "--check",
                "--ai",
                "--register",
                "--port",
                "9891",
                "--data-dir",
                str(tmp_path / "new"),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "private-test-key" not in output
    assert "未联网验证密钥有效性" in output and "不索取 163 授权码" in output
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "configuration",
    [
        {"DEEPSEEK_API_KEY": "", "LLM_TIMEOUT": 30},
        {"DEEPSEEK_API_KEY": "private-test-key", "LLM_TIMEOUT": 90},
    ],
)
def test_invalid_ai_configuration_is_actionable_and_redacted(
    configuration, monkeypatch, tmp_path, capsys
):
    monkeypatch.setitem(sys.modules, "config", SimpleNamespace(**configuration))
    assert coach_run.check_ready(tmp_path, 9891, ai=True) == 1
    output = capsys.readouterr().out
    assert "[需处理] AI 配置" in output
    assert "private-test-key" not in output
    assert list(tmp_path.iterdir()) == []


def test_configuration_import_failure_does_not_echo_exception(
    monkeypatch, tmp_path, capsys
):
    from coach import dialogue

    def failed_import():
        raise ValueError("private-test-value")

    monkeypatch.setattr(dialogue, "real_responder", failed_import)
    assert coach_run.check_ready(tmp_path, 9891, ai=True) == 1
    output = capsys.readouterr().out
    assert "private-test-value" not in output and "[需处理] AI 配置" in output


def test_missing_dependency_returns_fix_without_import_exception(
    monkeypatch, tmp_path, capsys
):
    original_import = coach_run.importlib.import_module

    def missing_pdf(name):
        if name == "pypdf":
            raise ImportError("private-test-value")
        return original_import(name)

    monkeypatch.setattr(coach_run.importlib, "import_module", missing_pdf)
    assert coach_run.check_ready(tmp_path, 9891) == 1
    output = capsys.readouterr().out
    assert "pypdf" in output and "pip install -r requirements.txt" in output
    assert "private-test-value" not in output


@pytest.mark.parametrize("marker", [b"simulated", b"unknown", b"\xff"])
def test_directory_mode_conflict_never_modifies_existing_files(
    marker, tmp_path, capsys
):
    (tmp_path / ".coach-mode").write_bytes(marker)
    (tmp_path / "users.db").write_bytes(b"untouched-existing-data")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert coach_run.check_ready(tmp_path, 9891) == 1
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    assert "模式冲突" in capsys.readouterr().out


def test_matching_directory_is_read_only(tmp_path):
    (tmp_path / ".coach-mode").write_text("real", encoding="utf-8")
    (tmp_path / "coach_conversations.db").write_bytes(b"untouched")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert coach_run.check_ready(tmp_path, 9891) == 0
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_directory_pointing_to_file_is_rejected(tmp_path, capsys):
    path = tmp_path / "file"
    path.write_bytes(b"untouched")
    assert coach_run.check_ready(path, 9891) == 1
    assert path.read_bytes() == b"untouched"
    assert "[需处理] 数据目录" in capsys.readouterr().out


def test_busy_port_returns_local_advice_without_starting(monkeypatch, tmp_path, capsys):
    class Busy(coach_run.socket.socket):
        def bind(self, address):
            raise OSError("private-test-value")

    monkeypatch.setattr(coach_run.socket, "socket", Busy)
    assert coach_run.check_ready(tmp_path / "new", 9891) == 1
    output = capsys.readouterr().out
    assert "--port" in output and "private-test-value" not in output
    assert list(tmp_path.iterdir()) == []
