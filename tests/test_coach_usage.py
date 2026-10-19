import sqlite3
from contextlib import closing

import pytest

from api import coach_usage
from conversation.coach_repository import CoachRepository
from tests.test_ai_usage import send


@pytest.fixture
def directory(tmp_path):
    root = tmp_path / "fictional-space"
    root.mkdir()
    (root / ".coach-mode").write_text("simulated", encoding="ascii")
    CoachRepository(root / "coach_conversations.db")
    return root


def test_show_is_read_only_and_set_changes_existing_limits_without_resetting_counts(
    directory, capsys
):
    repo = CoachRepository(directory / "coach_conversations.db")
    from time import time

    assert send(repo, now=int(time())) == "complete"
    before = repo.database_path.read_bytes()
    assert coach_usage.main(["show", "--data-dir", str(directory)]) == 0
    assert repo.database_path.read_bytes() == before
    assert "已受理 1 次" in capsys.readouterr().out
    assert (
        coach_usage.main(
            ["set", "--data-dir", str(directory), "--per-user", "1", "--total", "3"]
        )
        == 0
    )
    snapshot = repo.ai_usage("one")
    assert snapshot["used"] == 1 and snapshot["user_limit"] == 1
    assert send(repo, now=int(time())) == "daily_limit"
    assert (
        coach_usage.main(
            ["set", "--data-dir", str(directory), "--per-user", "3", "--total", "4"]
        )
        == 0
    )
    assert send(repo, now=int(time())) == "complete"
    assert CoachRepository(repo.database_path).ai_usage("one")["used"] == 2


def test_zero_pauses_ai_but_does_not_delete_conversation(directory):
    repo = CoachRepository(directory / "coach_conversations.db")
    assert send(repo) == "complete"
    assert (
        coach_usage.main(
            ["set", "--data-dir", str(directory), "--per-user", "0", "--total", "0"]
        )
        == 0
    )
    assert len(repo.conversation_records("one")) == 1
    assert send(repo) == "daily_limit"


@pytest.mark.parametrize(
    "args",
    [
        ["set"],
        ["set", "--per-user", "-1", "--total", "4"],
        ["set", "--per-user", "4", "--total", "2"],
        ["set", "--per-user", "10001", "--total", "10002"],
        ["show", "--total", "3"],
    ],
)
def test_bad_settings_do_not_mutate_database(directory, args):
    before = (directory / "coach_conversations.db").read_bytes()
    with pytest.raises(SystemExit):
        coach_usage.main([*args, "--data-dir", str(directory)])
    assert (directory / "coach_conversations.db").read_bytes() == before


def test_unknown_incomplete_and_wrong_mode_directories_are_not_created_or_modified(
    tmp_path, capsys
):
    unknown = tmp_path / "missing"
    assert (
        coach_usage.main(
            ["set", "--data-dir", str(unknown), "--per-user", "1", "--total", "2"]
        )
        == 1
    )
    assert not unknown.exists()
    for marker in ("bad", "real"):
        root = tmp_path / marker
        root.mkdir()
        (root / ".coach-mode").write_text(marker)
        CoachRepository(root / "coach_conversations.db")
        if marker == "real":
            (root / ".coach-restore-incomplete").touch()
        before = (root / "coach_conversations.db").read_bytes()
        assert coach_usage.main(["show", "--data-dir", str(root)]) == 1
        assert before == (root / "coach_conversations.db").read_bytes()
    assert "未创建新空间" in capsys.readouterr().out


def test_legacy_usage_show_does_not_migrate_or_create_tables(tmp_path, capsys):
    root = tmp_path / "legacy"
    root.mkdir()
    (root / ".coach-mode").write_text("real")
    path = root / "coach_conversations.db"
    with closing(sqlite3.connect(path)) as db, db:
        db.execute("CREATE TABLE coach_turns(turn_id INTEGER)")
    before = path.read_bytes()
    assert coach_usage.main(["show", "--data-dir", str(root)]) == 0
    assert path.read_bytes() == before
    assert "每日 100 次" in capsys.readouterr().out
