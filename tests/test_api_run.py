import builtins
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api import run as web_runner


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*arguments, working_dir, **environment):
    env = os.environ.copy()
    env.update(
        PYTHONPATH=str(PROJECT_ROOT),
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
        DEEPSEEK_API_KEY="",
    )
    env.update(environment)

    return subprocess.run(
        [sys.executable, "-B", "-m", "api.run", *arguments],
        cwd=working_dir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )


@pytest.mark.integration
def test_help_should_work_outside_project_without_creating_data(tmp_path):
    result = run_cli("--help", working_dir=tmp_path, LLM_TIMEOUT="invalid")

    assert result.returncode == 0
    assert "--port" in result.stdout
    assert "--data-dir" in result.stdout
    assert list(tmp_path.iterdir()) == []


@pytest.mark.unit
@pytest.mark.parametrize("port", ["0", "65536", "not-a-number"])
def test_invalid_port_should_explain_valid_range(port, capsys):
    with pytest.raises(SystemExit) as error:
        web_runner.main(["--port", port])

    assert error.value.code == 2
    assert "1 到 65535" in capsys.readouterr().err


@pytest.mark.unit
def test_missing_dependency_should_show_install_command(monkeypatch, capsys):
    original_import = builtins.__import__

    def import_without_uvicorn(name, *args, **kwargs):
        if name == "uvicorn":
            raise ModuleNotFoundError("uvicorn")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_uvicorn)

    assert web_runner.main([]) == 1
    assert "python -m pip install -r requirements.txt" in capsys.readouterr().err


@pytest.mark.integration
def test_invalid_environment_should_report_configuration_error(tmp_path):
    result = run_cli(
        "--data-dir",
        str(tmp_path / "data"),
        working_dir=tmp_path,
        LLM_TIMEOUT="invalid",
    )

    assert result.returncode == 1
    assert "配置格式不正确" in result.stderr
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "data").exists()


@pytest.mark.integration
def test_invalid_data_directory_should_report_database_error(tmp_path):
    data_file = tmp_path / "not-a-directory"
    data_file.write_text("keep this file", encoding="utf-8")

    result = run_cli("--data-dir", str(data_file), working_dir=tmp_path)

    assert result.returncode == 1
    assert "无法初始化数据库" in result.stderr
    assert data_file.read_text(encoding="utf-8") == "keep this file"


@pytest.mark.integration
def test_start_should_serve_homepage_without_api_key(tmp_path, monkeypatch, capsys):
    import config
    import uvicorn

    monkeypatch.setattr(config, "DEEPSEEK_API_KEY", None)
    observed = {}

    def inspect_server(app, host, port, log_level, access_log):
        assert access_log is False
        observed.update(host=host, port=port)
        response = TestClient(app).get("/")
        assert response.status_code == 200
        assert "AI Learning Coach" in response.text

    monkeypatch.setattr(uvicorn, "run", inspect_server)
    monkeypatch.chdir(tmp_path)
    # The default location must not follow a different shell working directory.
    monkeypatch.setattr(web_runner, "PROJECT_ROOT", tmp_path / "project")

    assert web_runner.main(["--port", "8123"]) == 0
    assert observed == {"host": "127.0.0.1", "port": 8123}
    assert (tmp_path / "project" / "data" / "users.db").exists()
    assert not (tmp_path / "data").exists()
    output = capsys.readouterr().out
    assert "http://127.0.0.1:8123" in output
    assert "未配置 DEEPSEEK_API_KEY" in output


@pytest.mark.integration
def test_server_start_failure_should_show_alternative_port(
    tmp_path, monkeypatch, capsys
):
    import uvicorn

    def fail_to_bind(*args, **kwargs):
        raise SystemExit(1)

    monkeypatch.setattr(uvicorn, "run", fail_to_bind)

    assert web_runner.main(["--data-dir", str(tmp_path)]) == 1
    assert "python -m api.run --port 8001" in capsys.readouterr().err
