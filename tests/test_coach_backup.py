import builtins
import sqlite3
from zipfile import BadZipFile

import pytest

from api import coach_backup
from core.local_data_lock import DataDirectoryBusy, RestoreIncomplete
from tests import test_local_backup as fixtures

space = fixtures.space
password_hash = fixtures.password_hash


def test_operator_create_check_restore_commands_with_fictional_data(
    space, tmp_path, capsys, monkeypatch
):
    root, _, _, _, _ = space
    output, target = tmp_path / "my.zip", tmp_path / "coach-restored-demo"
    monkeypatch.setattr(
        builtins, "input", lambda *a: pytest.fail("no credential prompt")
    )
    assert (
        coach_backup.main(["create", "--data-dir", str(root), "--output", str(output)])
        == 0
    )
    assert coach_backup.main(["check", str(output)]) == 0
    assert coach_backup.main(["restore", str(output), "--target", str(target)]) == 0
    text = capsys.readouterr().out
    assert "检查通过" in text and "备份时的邮箱和密码" in text
    assert "one@example.com" not in text and "$argon2" not in text


@pytest.mark.parametrize(
    "error",
    [
        OSError("private-path-secret"),
        sqlite3.DatabaseError("private-data-secret"),
        BadZipFile("private-zip-secret"),
        ValueError("private-format-secret"),
        DataDirectoryBusy(),
        RestoreIncomplete(),
    ],
)
def test_cli_errors_do_not_expose_raw_details(monkeypatch, capsys, error):
    def failed(*a):
        raise error

    monkeypatch.setattr(coach_backup, "check_backup", failed)
    assert coach_backup.main(["check", "fictional.zip"]) == 1
    assert "secret" not in capsys.readouterr().out


def test_defaults_do_not_start_web_ai_or_prompt(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(
        coach_backup, "create_backup", lambda *a: calls.append(a) or a[1]
    )
    assert coach_backup.main(["create"]) == 0
    assert calls[0][0] == coach_backup.ROOT / "data/coach-local"
    assert calls[0][1].parent == coach_backup.ROOT / "data/coach-backups"
    assert calls[0][1].suffix == ".zip"
    assert "私人" in capsys.readouterr().out


def test_simulated_restore_reports_required_mode(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        coach_backup, "restore_backup", lambda *a: {"mode": "simulated"}
    )
    assert (
        coach_backup.main(
            ["restore", "fictional.zip", "--target", str(tmp_path / "new")]
        )
        == 0
    )
    assert "--simulate" in capsys.readouterr().out
