import json
import secrets
import sqlite3
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED, BadZipFile

import pytest
from fastapi.testclient import TestClient

from api.account_app import create_account_app
from coach import local_backup as backup
from coach.materials import MaterialRepository
from conversation.coach_repository import CoachRepository
from core.local_data_lock import (
    data_directory_lock,
    DataDirectoryBusy,
    RestoreIncomplete,
)
from security.passwords import hash_password
from tests.test_web_coach_dialogue import add_user, login, PASSWORD, LEARNING


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def space(tmp_path, password_hash):
    root = tmp_path / "space"
    user = add_user(root, password_hash, "one@example.com", "虚构备份学习者")
    add_user(root, password_hash, "two@example.com", "第二位虚构学习者")
    (root / ".coach-mode").write_text("real", encoding="ascii")
    materials = MaterialRepository(root / "coach_library.db")
    material = materials.add(
        user.user_id, "book.txt", "原书独有段落，讨论间隔重温。".encode()
    )
    materials.select(user.user_id, material)
    repo = CoachRepository(root / "coach_conversations.db", materials=materials)
    nonce = secrets.token_urlsafe(32)
    repo.claim(user.user_id, nonce, "请整理一本教案", now=1000)
    repo.finish(
        user.user_id,
        nonce,
        "虚构回复。",
        LEARNING,
        now=1001,
        draft={"title": "第一版教案", "topic": "学习", "content": "最初的正文。"},
    )
    lesson = repo.list_knowledge(user.user_id, status="pending")[0]["knowledge_id"]
    repo.confirm_knowledge(user.user_id, lesson)
    repo.revise_knowledge(
        user.user_id, lesson, 1, title="第二版教案", content="当前的正文。"
    )
    repo.add_memory(user.user_id, "希望解释时多用日常例子。")
    book = uuid4().hex
    repo.create_booklet(user.user_id, book, "我的知识资产")
    repo.change_booklet(user.user_id, book, 1, "add", knowledge_id=lesson)
    repo.remember_booklet_position(user.user_id, book, 2, lesson, 0)
    return root, user, material, lesson, book


def hashes(root):
    return {name: backup._hash(root / name) for name in backup.FILES}


def test_create_check_restore_preserves_assets_and_original_password_login(
    space, tmp_path
):
    root, user, material, lesson, book = space
    before = hashes(root)
    # Files outside the explicit data whitelist never enter the archive.
    (root / ".env").write_text("NOT-A-REAL-SECRET", encoding="ascii")
    output = backup.create_backup(root, tmp_path / "my-backup.zip")
    assert hashes(root) == before
    with ZipFile(output) as archive:
        assert set(archive.namelist()) == {*backup.FILES, "manifest.json"}
        manifest = json.loads(archive.read("manifest.json"))
        assert (
            "one@example.com" not in json.dumps(manifest)
            and ".env" not in manifest["files"]
        )
    assert backup.check_backup(output)["databases"] == 3
    target = tmp_path / "restored"
    assert backup.restore_backup(output, target)["mode"] == "real"
    assert hashes(root) == before
    repo = CoachRepository(target / "coach_conversations.db")
    assert repo.knowledge(user.user_id, lesson)["content"] == "当前的正文。"
    assert repo.knowledge_version(user.user_id, lesson, 1)["content"] == "最初的正文。"
    assert (
        repo.booklet(user.user_id, book, chapter="resume")["reading_position"][
            "knowledge_id"
        ]
        == lesson
    )
    assert repo.list_memories(user.user_id)[0]["content"] == "希望解释时多用日常例子。"
    restored_materials = MaterialRepository(target / "coach_library.db")
    assert restored_materials.selected(user.user_id)["material_id"] == material
    with sqlite3.connect(target / "coach_library.db") as db:
        assert (
            db.execute(
                "SELECT raw FROM materials WHERE material_id=?", (material,)
            ).fetchone()[0]
            == "原书独有段落，讨论间隔重温。".encode()
        )
    with TestClient(
        create_account_app(target), base_url="https://coach.example.com"
    ) as client:
        page = login(client)
        assert "虚构备份学习者" in page.text and "虚构回复" in page.text
        assert "第二版教案" in client.get("/web/knowledge").text
        assert "当前的正文" in client.get(f"/web/booklets/{book}").text


def test_restoration_invalidates_sessions_tokens_and_unfinished_replies(
    space, tmp_path
):
    root, user, _, _, _ = space
    with TestClient(
        create_account_app(root), base_url="https://coach.example.com"
    ) as client:
        login(client)
        token = client.cookies.get("coach_login_session")
    repo = CoachRepository(root / "coach_conversations.db")
    repo.claim(user.user_id, secrets.token_urlsafe(32), "未完成消息", now=1002)
    with sqlite3.connect(root / "users.db") as db:
        db.execute(
            "INSERT INTO password_reset_tokens VALUES(?,?,?,?,?)",
            (user.user_id, user.email, "a" * 64, 1000, 9999999999),
        )
        password = db.execute(
            "SELECT password_hash FROM user_passwords WHERE user_id=?", (user.user_id,)
        ).fetchone()[0]
        request_id = "p" * 45
        db.execute(
            "INSERT INTO pending_registrations VALUES(?,?,?,?,?,?)",
            (
                request_id,
                "未完成注册",
                "pending@example.com",
                password,
                1000,
                9999999999,
            ),
        )
        db.execute(
            "INSERT INTO registration_email_verifications VALUES(?,?,?,?)",
            (request_id, "b" * 64, 1000, 9999999999),
        )
        db.execute(
            "INSERT INTO registration_browser_bindings VALUES(?,?)",
            (request_id, "c" * 64),
        )
        db.execute(
            "INSERT INTO registration_mail_deliveries VALUES(?,?,?)",
            (request_id, "d" * 32, "accepted"),
        )
        db.execute(
            "UPDATE user_email_verifications SET token_hash=? WHERE user_id=?",
            ("e" * 64, user.user_id),
        )
    before = hashes(root)
    output = backup.create_backup(root, tmp_path / "pending.zip")
    target = tmp_path / "restored"
    backup.restore_backup(output, target)
    assert hashes(root) == before
    with sqlite3.connect(target / "users.db") as db:
        for table in (
            "pending_registrations",
            "registration_email_verifications",
            "registration_browser_bindings",
            "registration_mail_deliveries",
        ):
            assert db.execute("SELECT COUNT(*) FROM " + table).fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM login_sessions").fetchone()[0] == 0
        assert (
            db.execute("SELECT COUNT(*) FROM password_reset_tokens").fetchone()[0] == 0
        )
        assert (
            db.execute(
                "SELECT COUNT(*) FROM user_email_verifications WHERE token_hash IS NOT NULL"
            ).fetchone()[0]
            == 0
        )
    with sqlite3.connect(target / "coach_conversations.db") as db:
        assert (
            db.execute(
                "SELECT status FROM coach_turns WHERE user_content='未完成消息'"
            ).fetchone()[0]
            == "failed"
        )
    with TestClient(
        create_account_app(target), base_url="https://coach.example.com"
    ) as fresh:
        fresh.cookies.set("coach_login_session", token)
        assert fresh.get("/web/welcome", follow_redirects=False).status_code == 303
        fresh.cookies.clear()
        assert login(fresh).status_code == 200


@pytest.mark.parametrize("existing", ["file", "empty", "nonempty", "source"])
def test_restore_never_overwrites_existing_target(space, tmp_path, existing):
    root, _, _, _, _ = space
    output = backup.create_backup(root, tmp_path / "safe.zip")
    target = root if existing == "source" else tmp_path / "target"
    if existing == "file":
        target.write_text("retain", encoding="ascii")
    elif existing == "empty":
        target.mkdir()
    elif existing == "nonempty":
        target.mkdir()
        (target / "keep.txt").write_text("retain", encoding="ascii")
    before = hashes(root)
    with pytest.raises(backup.BackupError, match="新目录"):
        backup.restore_backup(output, target)
    assert hashes(root) == before
    if existing == "file":
        assert target.read_text() == "retain"
    if existing == "nonempty":
        assert (target / "keep.txt").read_text() == "retain"


def mutated_archive(original, output, change):
    with ZipFile(original) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files["manifest.json"])
    change(files, manifest)
    files["manifest.json"] = json.dumps(manifest).encode()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return output


@pytest.mark.parametrize(
    "bad",
    [
        "checksum",
        "size",
        "extra-path",
        "missing",
        "version",
        "mode-type",
        "mode-size",
        "bad-schema",
        "view",
        "duplicate",
    ],
)
def test_invalid_archive_is_rejected_before_target_is_created(space, tmp_path, bad):
    root, _, _, _, _ = space
    original = backup.create_backup(root, tmp_path / "good.zip")

    def change(files, manifest):
        if bad == "checksum":
            manifest["files"]["users.db"]["sha256"] = "0" * 64
        if bad == "size":
            manifest["files"]["users.db"]["bytes"] += 1
        if bad == "extra-path":
            files["../outside.txt"] = b"unsafe"
        if bad == "missing":
            del files["users.db"]
        if bad == "version":
            manifest["version"] = True
        if bad == "mode-type":
            manifest["mode"] = []
        if bad == "mode-size":
            manifest["files"][".coach-mode"]["bytes"] = backup.MAX_BYTES
        if bad in {"bad-schema", "view"}:
            staged = tmp_path / "changed.db"
            staged.write_bytes(files["users.db"])
            with sqlite3.connect(staged) as db:
                if bad == "bad-schema":
                    db.execute("DROP TABLE user_passwords")
                else:
                    db.execute("CREATE VIEW disallowed AS SELECT name FROM users")
            files["users.db"] = staged.read_bytes()
            manifest["files"]["users.db"] = {
                "bytes": len(files["users.db"]),
                "sha256": backup._hash(staged),
            }

    broken = mutated_archive(original, tmp_path / "bad.zip", change)
    if bad == "duplicate":
        with ZipFile(broken, "a") as archive:
            with pytest.warns(UserWarning):
                archive.writestr(".coach-mode", b"real")
    target = tmp_path / "target"
    with pytest.raises((backup.BackupError, BadZipFile)):
        backup.restore_backup(broken, target)
    assert not target.exists() and not (tmp_path / "outside.txt").exists()


def test_source_busy_incomplete_missing_and_existing_backup_are_protected(
    space, tmp_path
):
    root, _, _, _, _ = space
    with data_directory_lock(root):
        with pytest.raises(DataDirectoryBusy):
            backup.create_backup(root, tmp_path / "busy.zip")
    assert not (tmp_path / "busy.zip").exists()
    (root / ".coach-restore-incomplete").write_text("incomplete")
    with pytest.raises(RestoreIncomplete):
        backup.create_backup(root, tmp_path / "incomplete.zip")
    (root / ".coach-restore-incomplete").unlink()
    output = backup.create_backup(root, tmp_path / "existing.zip")
    before = output.read_bytes()
    with pytest.raises(backup.BackupError):
        backup.create_backup(root, output)
    assert output.read_bytes() == before
    with pytest.raises(backup.BackupError):
        backup.create_backup(root, root / "inside.zip")
    with pytest.raises(backup.BackupError):
        backup.create_backup(tmp_path / "missing", tmp_path / "missing.zip")
    assert not (tmp_path / "missing").exists()


def test_interrupted_restore_is_marked_and_cannot_start(space, tmp_path, monkeypatch):
    from api import coach_run

    root, _, _, _, _ = space
    output = backup.create_backup(root, tmp_path / "safe.zip")
    original = backup._publish_file

    def failing(source, target):
        if target.name == "coach_library.db":
            raise OSError("fictional failure")
        original(source, target)

    monkeypatch.setattr(backup, "_publish_file", failing)
    target = tmp_path / "interrupted"
    with pytest.raises(OSError):
        backup.restore_backup(output, target)
    assert (target / ".coach-restore-incomplete").exists()
    monkeypatch.setattr(
        coach_run,
        "build_app",
        lambda *a, **k: pytest.fail("must not boot partial restore"),
    )
    with pytest.raises(RestoreIncomplete):
        coach_run._serve(target, 0)


def test_committed_wal_rows_are_included_without_replacing_source_files(
    space, tmp_path
):
    root, user, _, _, _ = space
    with sqlite3.connect(root / "coach_conversations.db") as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            "INSERT INTO coach_memories VALUES(?,?,?,1,1000,1000)",
            (uuid4().hex, user.user_id, "WAL 内已提交的记忆"),
        )
        db.commit()
        output = backup.create_backup(root, tmp_path / "wal.zip")
    target = tmp_path / "restored"
    backup.restore_backup(output, target)
    assert any(
        row["content"] == "WAL 内已提交的记忆"
        for row in CoachRepository(target / "coach_conversations.db").list_memories(
            user.user_id
        )
    )


def test_fallback_without_hard_links_still_creates_and_restores_exclusively(
    space, tmp_path, monkeypatch
):
    root, _, _, _, _ = space
    monkeypatch.setattr(
        backup.os, "link", lambda *a: (_ for _ in ()).throw(OSError("unsupported"))
    )
    output = backup.create_backup(root, tmp_path / "copied.zip")
    target = tmp_path / "copied-space"
    assert backup.restore_backup(output, target)["databases"] == 3
    assert (target / ".coach-mode").read_text() == "real"


def test_capacity_and_copy_deadline_fail_without_publishing_a_backup(
    space, tmp_path, monkeypatch
):
    root, _, _, _, _ = space
    before = hashes(root)
    with monkeypatch.context() as limited:
        limited.setattr(backup, "MAX_BYTES", 100)
        with pytest.raises(backup.BackupError, match="512 MB"):
            backup.create_backup(root, tmp_path / "oversize.zip")
    ticks = iter((0, 31))
    monkeypatch.setattr(backup, "monotonic", lambda: next(ticks))
    with pytest.raises(backup.BackupError, match="超时"):
        backup.create_backup(root, tmp_path / "timeout.zip")
    assert (
        not (tmp_path / "oversize.zip").exists()
        and not (tmp_path / "timeout.zip").exists()
    )
    assert hashes(root) == before


def test_failed_fallback_copy_removes_only_its_new_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(
        backup.os, "link", lambda *a: (_ for _ in ()).throw(OSError("unsupported"))
    )
    output = tmp_path / "new.zip"
    with pytest.raises(FileNotFoundError):
        backup._publish_file(tmp_path / "missing.zip", output)
    assert not output.exists()
    output.write_text("existing", encoding="ascii")
    with pytest.raises(FileExistsError):
        backup._publish_file(tmp_path / "missing.zip", output)
    assert output.read_text() == "existing"
