import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from coach.draft_edit import draft_version
from conversation.coach_repository import CoachRepository
from tests.test_draft_edit import seed


def removed(repo, identity):
    current = repo.knowledge("one", identity)
    assert (
        repo.change_draft("one", identity, "dismiss", draft_version(current))
        == "dismissed"
    )
    return repo.knowledge("one", identity, include_dismissed=True)


def test_recovery_preserves_content_sources_learning_and_usage_across_restart(tmp_path):
    repo, identity, original = seed(tmp_path)
    before = repo.view("one", now=1002)
    usage = repo.ai_usage("one", now=1002)
    item = removed(repo, identity)
    assert repo.knowledge("one", identity) is None
    assert repo.restore_draft("one", identity, draft_version(item)) == "restored"
    restarted = CoachRepository(repo.database_path)
    current = restarted.knowledge("one", identity)
    assert {k: v for k, v in current.items() if k != "draft_generation"} == {
        k: v for k, v in original.items() if k != "draft_generation"
    }
    assert current["draft_generation"] == 1
    assert current["saved_at"] is None and current["status"] == "pending"
    assert restarted.view("one", now=1002) == before
    assert restarted.ai_usage("one", now=1002) == usage
    assert (
        restarted.knowledge("one", identity, saved_only=True, include_dismissed=True)
        is None
    )
    assert restarted.knowledge_versions("one", identity) == []
    assert restarted.list_knowledge("one") == []
    assert restarted.list_knowledge("one", status="dismissed") == []
    assert (
        restarted.list_knowledge("one", status="pending")[0]["knowledge_id"] == identity
    )


@pytest.mark.parametrize("operation", ["stage", "save", "dismiss"])
def test_pre_removal_forms_stay_stale_after_identical_restore_and_repeated_cycles(
    tmp_path, operation
):
    repo, identity, original = seed(tmp_path)
    first_removed = removed(repo, identity)
    repo.restore_draft("one", identity, draft_version(first_removed))
    current = repo.knowledge("one", identity)
    assert (
        repo.change_draft(
            "one",
            identity,
            operation,
            draft_version(original),
            title="旧页面",
            content="不允许覆盖",
        )
        == "conflict"
    )
    assert repo.knowledge("one", identity) == current
    second_removed = removed(repo, identity)
    assert (
        repo.restore_draft("one", identity, draft_version(first_removed)) == "conflict"
    )
    assert (
        repo.restore_draft("one", identity, draft_version(second_removed)) == "restored"
    )
    assert (
        repo.change_draft(
            "one",
            identity,
            operation,
            draft_version(current),
            title="旧页面",
            content="不允许覆盖",
        )
        == "conflict"
    )
    assert repo.knowledge("one", identity)["draft_generation"] == 2


def test_recovery_is_owned_explicit_idempotent_and_cannot_demote_saved(tmp_path):
    repo, identity, _ = seed(tmp_path)
    item = removed(repo, identity)
    before = repo.database_path.read_bytes()
    assert repo.restore_draft("two", identity, draft_version(item)) == "missing"
    assert repo.knowledge("two", identity, include_dismissed=True) is None
    assert repo.restore_draft("one", identity, "0" * 64) == "conflict"
    assert repo.database_path.read_bytes() == before
    assert repo.restore_draft("one", identity, draft_version(item)) == "restored"
    current = repo.knowledge("one", identity)
    before = repo.database_path.read_bytes()
    assert repo.restore_draft("one", identity, draft_version(item)) == "processed"
    assert repo.database_path.read_bytes() == before
    repo.change_draft(
        "one",
        identity,
        "save",
        draft_version(current),
        title=current["title"],
        content=current["content"],
    )
    saved = repo.knowledge("one", identity)
    assert repo.restore_draft("one", identity, draft_version(item)) == "processed"
    assert repo.knowledge("one", identity) == saved


def test_recovery_has_one_concurrent_winner_and_atomic_generation(tmp_path):
    repo, identity, _ = seed(tmp_path)
    item = removed(repo, identity)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: repo.restore_draft("one", identity, draft_version(item)),
                range(2),
            )
        )
    assert sorted(results) == ["processed", "restored"]
    assert repo.knowledge("one", identity)["draft_generation"] == 1
    item = removed(repo, identity)
    with closing(repo._connect()) as db, db:
        db.execute(
            "CREATE TRIGGER stop_restore BEFORE UPDATE ON coach_draft_restores BEGIN SELECT RAISE(ABORT,'test only'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        repo.restore_draft("one", identity, draft_version(item))
    assert repo.knowledge("one", identity, include_dismissed=True) == item


def test_old_database_initializes_empty_generation_and_recovers_historical_draft(
    tmp_path,
):
    repo, identity, _ = seed(tmp_path)
    repo.confirm_knowledge("one", identity, save=False)
    with closing(repo._connect()) as db, db:
        db.execute("DROP TABLE coach_draft_restores")
    legacy = CoachRepository(repo.database_path)
    item = legacy.knowledge("one", identity, include_dismissed=True)
    assert item["draft_generation"] == 0
    assert legacy.restore_draft("one", identity, draft_version(item)) == "restored"


@pytest.mark.parametrize("version", [None, "", "a" * 63, "A" * 64, "g" * 64])
def test_bad_versions_do_not_write(tmp_path, version):
    repo, identity, _ = seed(tmp_path)
    item = removed(repo, identity)
    with pytest.raises(ValueError):
        repo.restore_draft("one", identity, version)
    assert repo.knowledge("one", identity, include_dismissed=True) == item
