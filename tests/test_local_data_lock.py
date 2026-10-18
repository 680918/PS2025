import subprocess
import sys
from pathlib import Path

import pytest

from core.local_data_lock import (
    data_directory_lock,
    DataDirectoryBusy,
    RestoreIncomplete,
)


def test_exclusion_and_release_without_deleting_persistent_lock_file(tmp_path):
    with data_directory_lock(tmp_path):
        with pytest.raises(DataDirectoryBusy):
            with data_directory_lock(tmp_path):
                pass
        code = "from pathlib import Path; import sys; from core.local_data_lock import data_directory_lock, DataDirectoryBusy\ntry:\n with data_directory_lock(Path(sys.argv[1])): sys.exit(3)\nexcept DataDirectoryBusy: sys.exit(0)"
        assert (
            subprocess.run(
                [sys.executable, "-c", code, str(tmp_path)],
                cwd=Path(__file__).resolve().parents[1],
                timeout=15,
            ).returncode
            == 0
        )
    assert (tmp_path / ".coach.lock").exists()
    with data_directory_lock(tmp_path):
        pass


def test_exception_releases_lock(tmp_path):
    with pytest.raises(ValueError):
        with data_directory_lock(tmp_path):
            raise ValueError("fictional")
    with data_directory_lock(tmp_path):
        pass


def test_runner_refuses_busy_data_before_constructing_app(tmp_path, monkeypatch):
    from api import coach_run

    monkeypatch.setattr(
        coach_run, "build_app", lambda *a, **k: pytest.fail("no app when busy")
    )
    with data_directory_lock(tmp_path):
        with pytest.raises(DataDirectoryBusy):
            coach_run._serve(tmp_path, 0)
    assert not (tmp_path / ".coach-mode").exists()


def test_runner_holds_lock_during_app_and_server_lifetime(tmp_path, monkeypatch):
    import uvicorn
    from api import coach_run

    def protected(*a, **k):
        with pytest.raises(DataDirectoryBusy):
            with data_directory_lock(tmp_path):
                pass
        return object()

    class Server:
        def __init__(self, config):
            pass

        def run(self, **kwargs):
            protected()

    monkeypatch.setattr(coach_run, "build_app", protected)
    monkeypatch.setattr(uvicorn, "Server", Server)
    assert coach_run._serve(tmp_path, 0) == 0
    with data_directory_lock(tmp_path):
        pass


def test_incomplete_restore_check_is_read_only_and_main_reports_fixed_message(
    tmp_path, monkeypatch, capsys
):
    from api import coach_run

    (tmp_path / ".coach-restore-incomplete").write_text("incomplete")
    (tmp_path / ".coach-mode").write_text("real")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert coach_run.check_ready(tmp_path, 0) == 1
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    monkeypatch.setattr(
        coach_run, "_serve", lambda *a, **k: (_ for _ in ()).throw(RestoreIncomplete())
    )
    assert coach_run.main([]) == 1
    assert "恢复尚未完成" in capsys.readouterr().out
