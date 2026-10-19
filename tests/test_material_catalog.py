import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from coach.materials import MaterialError, MaterialRepository


def test_rename_preserves_original_chunks_selection_and_quota_after_restart(tmp_path):
    path = tmp_path / "library.db"
    repo = MaterialRepository(path)
    raw = "# 阅读\n学过的知识要回想与应用。".encode()
    identity = repo.add("owner", "original.md", raw, title="旧名称")
    repo.select("owner", identity)
    before, chunks = repo.get("owner", identity), repo.chunks("owner", identity)
    assert repo.rename("owner", identity, "  我的阅读笔记  ", expected_title="旧名称")
    restarted = MaterialRepository(path)
    after = restarted.selected("owner")
    assert after == {**before, "title": "我的阅读笔记"}
    assert after["raw_bytes"] == len(raw)
    assert restarted.chunks("owner", identity) == chunks
    assert restarted.add("owner", "again.md", raw, title="不覆盖改名") == identity
    assert restarted.get("owner", identity)["title"] == "我的阅读笔记"
    assert len(restarted.list("owner")) == 1
    with closing(sqlite3.connect(path)) as db:
        assert db.execute("SELECT raw FROM materials").fetchone()[0] == raw


def test_owner_scope_and_missing_material_do_not_write(tmp_path):
    repo = MaterialRepository(tmp_path / "library.db")
    identity = repo.add("one", "note.txt", b"my note", title="Private")
    for owner, key in (("two", identity), ("one", "f" * 32)):
        with pytest.raises(MaterialError, match="找不到"):
            repo.rename(owner, key, "Changed", expected_title="Private")
    assert repo.list("two") == []
    assert repo.get("one", identity)["title"] == "Private"


@pytest.mark.parametrize(
    "title", ["", "   ", "字" * 121, "bad\nname", "bad\x00name", "bad\ud800", None, 1]
)
def test_invalid_name_does_not_change_saved_title(tmp_path, title):
    repo = MaterialRepository(tmp_path / "library.db")
    identity = repo.add("one", "a.txt", b"text", title="Original")
    with pytest.raises(MaterialError):
        repo.rename("one", identity, title, expected_title="Original")
    assert repo.get("one", identity)["title"] == "Original"


def test_concurrent_editors_cannot_silently_overwrite(tmp_path):
    repo = MaterialRepository(tmp_path / "library.db")
    identity = repo.add("one", "a.txt", b"text", title="Original")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda title: repo.rename(
                    "one", identity, title, expected_title="Original"
                ),
                ["First", "Second"],
            )
        )
    assert sorted(results) == [False, True]
    current = repo.get("one", identity)["title"]
    assert current in {"First", "Second"}
    assert repo.rename("one", identity, current, expected_title=current)
