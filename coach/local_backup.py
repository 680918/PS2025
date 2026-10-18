"""Explicit, local whole-space backups. No web route, model or mail dependency."""

import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic, time
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

from core.local_data_lock import data_directory_lock, RestoreIncomplete

ROOT = Path(__file__).resolve().parents[1]
DATABASES = ("users.db", "coach_library.db", "coach_conversations.db")
FILES = (*DATABASES, ".coach-mode")
MAX_BYTES = 512 * 1024**2
MAX_MANIFEST = 16384
FORMAT = "zhixing-local-backup"
REQUIRED = {
    "users.db": {
        "users": {"user_id", "name", "email"},
        "user_passwords": {"user_id", "password_hash"},
        "user_email_verifications": {"user_id", "email", "verified_at", "token_hash"},
    },
    "coach_library.db": {
        "materials": {"material_id", "user_id", "raw"},
        "material_chunks": {"chunk_id", "material_id", "content"},
        "selected_material": {"user_id", "material_id"},
    },
    "coach_conversations.db": {
        "coach_turns": {"turn_id", "user_id", "status", "completed_at"},
        "coach_knowledge": {"knowledge_id", "user_id", "status", "content"},
        "coach_learning": {"user_id", "topic"},
    },
}


class BackupError(ValueError):
    pass


def _hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for piece in iter(lambda: stream.read(1024**2), b""):
            digest.update(piece)
    return digest.hexdigest()


def _publish_file(source, target):
    """Publish exclusively; copying supports drives without hard links."""
    try:
        os.link(source, target)
        return
    except FileExistsError:
        raise
    except OSError:
        pass
    created = False
    try:
        with target.open("xb") as output:
            created = True
            with source.open("rb") as original:
                shutil.copyfileobj(original, output, 1024**2)
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise


def _read(path):
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=1)
    db.execute("PRAGMA query_only=ON")
    db.execute("PRAGMA trusted_schema=OFF")
    return db


def _database_ok(path, name):
    with closing(_read(path)) as db:
        deadline = monotonic() + 30
        db.set_progress_handler(lambda: int(monotonic() > deadline), 10000)
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise BackupError("数据库完整性检查未通过。")
        objects = db.execute(
            "SELECT type,sql FROM sqlite_master WHERE type IN ('table','view','trigger')"
        ).fetchall()
        if any(
            kind in {"view", "trigger"} or "CREATE VIRTUAL TABLE" in (sql or "").upper()
            for kind, sql in objects
        ):
            raise BackupError("备份含不支持的数据库对象，未恢复。")
        for table, columns in REQUIRED[name].items():
            actual = {row[1] for row in db.execute("PRAGMA table_info(" + table + ")")}
            if not columns <= actual:
                raise BackupError("备份数据库结构不符合当前本机成长空间。")
        if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise BackupError("数据库关联完整性检查未通过。")


def _backup_copy(source, target):
    deadline = monotonic() + 30
    with closing(_read(source)) as original, closing(sqlite3.connect(target)) as copied:
        page_size = original.execute("PRAGMA page_size").fetchone()[0]

        def progress(status, remaining, total):
            if (
                status in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
                or monotonic() > deadline
            ):
                raise BackupError("数据库正在写入或读取超时，请停止本机服务后重试。")
            if total * page_size > MAX_BYTES:
                raise BackupError("备份超过本机工具的 512 MB 上限。")

        original.backup(copied, pages=256, progress=progress, sleep=0.01)
        copied.execute("PRAGMA journal_mode=DELETE")


def _extract_checked(archive, directory):
    archive = Path(archive).expanduser().resolve()
    if not archive.is_file() or archive.stat().st_size > MAX_BYTES + 1024**2:
        raise BackupError("备份文件不存在或超过 512 MB 上限。")
    with ZipFile(archive) as package:
        entries = package.infolist()
        if len(entries) != 5 or {entry.filename for entry in entries} != {
            *FILES,
            "manifest.json",
        }:
            raise BackupError("不是支持的本机备份包；个人阅读导出包不能用于恢复。")
        for entry in entries:
            kind = stat.S_IFMT(entry.external_attr >> 16)
            if (
                kind not in (0, stat.S_IFREG)
                or entry.flag_bits & 1
                or entry.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
            ):
                raise BackupError("备份包含不支持的文件类型。")
        if package.getinfo("manifest.json").file_size > MAX_MANIFEST:
            raise BackupError("备份清单无法读取。")
        manifest = json.loads(package.read("manifest.json"))
        if (
            not isinstance(manifest, dict)
            or manifest.get("format") != FORMAT
            or type(manifest.get("version")) is not int
            or manifest["version"] != 1
            or not isinstance(manifest.get("mode"), str)
            or manifest["mode"] not in {"real", "simulated"}
            or not isinstance(manifest.get("files"), dict)
            or set(manifest["files"]) != set(FILES)
        ):
            raise BackupError("备份格式或版本不受支持。")
        total = 0
        for name in FILES:
            record = manifest["files"][name]
            if (
                not isinstance(record, dict)
                or set(record) != {"bytes", "sha256"}
                or type(record["bytes"]) is not int
                or not 0 < record["bytes"] <= MAX_BYTES
                or not isinstance(record["sha256"], str)
                or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
            ):
                raise BackupError("备份清单无法核对。")
            total += record["bytes"]
            if name == ".coach-mode" and record["bytes"] != len(manifest["mode"]):
                raise BackupError("备份运行模式无法核对。")
            if total > MAX_BYTES or package.getinfo(name).file_size != record["bytes"]:
                raise BackupError("备份大小不符或超过 512 MB 上限。")
            written = 0
            digest = hashlib.sha256()
            with package.open(name) as source, (directory / name).open("xb") as target:
                for piece in iter(lambda: source.read(1024**2), b""):
                    written += len(piece)
                    if written > record["bytes"]:
                        raise BackupError("备份内容大小不符。")
                    digest.update(piece)
                    target.write(piece)
            if written != record["bytes"] or digest.hexdigest() != record["sha256"]:
                raise BackupError("备份校验失败，文件可能损坏。")
        if (directory / ".coach-mode").read_bytes() != manifest["mode"].encode():
            raise BackupError("备份运行模式不符。")
        for name in DATABASES:
            _database_ok(directory / name, name)
        return {"mode": manifest["mode"], "bytes": total, "databases": 3}


def check_backup(archive):
    with tempfile.TemporaryDirectory(prefix="coach-backup-check-") as temporary:
        return _extract_checked(archive, Path(temporary))


def create_backup(directory, destination):
    directory = Path(directory).expanduser().resolve()
    destination = Path(destination).expanduser().absolute()
    if not directory.is_dir() or any(
        not (directory / name).is_file() or (directory / name).is_symlink()
        for name in FILES
    ):
        raise BackupError("数据目录不完整，请核对已使用的本机成长空间目录。")
    if (
        destination.exists()
        or destination.is_symlink()
        or destination.suffix.lower() != ".zip"
    ):
        raise BackupError("请指定一个不存在的 .zip 备份文件。")
    if (
        directory == destination.parent.resolve()
        or directory in destination.parent.resolve().parents
    ):
        raise BackupError("备份需要放在成长空间数据目录之外。")
    with data_directory_lock(directory):
        if (directory / ".coach-restore-incomplete").exists():
            raise RestoreIncomplete
        if (directory / ".coach-mode").stat().st_size > 16:
            raise BackupError("数据目录运行模式无法读取。")
        mode = (directory / ".coach-mode").read_bytes()
        if mode not in (b"real", b"simulated"):
            raise BackupError("数据目录运行模式无法读取。")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".coach-backup-", dir=destination.parent
        ) as temporary:
            work = Path(temporary)
            for name in DATABASES:
                if (directory / name).stat().st_size > MAX_BYTES:
                    raise BackupError("备份超过本机工具的 512 MB 上限。")
                _backup_copy(directory / name, work / name)
                _database_ok(work / name, name)
            (work / ".coach-mode").write_bytes(mode)
            total = sum((work / name).stat().st_size for name in FILES)
            if total > MAX_BYTES:
                raise BackupError("备份超过本机工具的 512 MB 上限。")
            manifest = {
                "format": FORMAT,
                "version": 1,
                "mode": mode.decode(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "app_version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
                "files": {
                    name: {
                        "bytes": (work / name).stat().st_size,
                        "sha256": _hash(work / name),
                    }
                    for name in FILES
                },
            }
            bundle = work / "backup.zip"
            with ZipFile(bundle, "x", compression=ZIP_DEFLATED) as package:
                package.writestr(
                    "manifest.json", json.dumps(manifest, ensure_ascii=False)
                )
                for name in FILES:
                    package.write(work / name, name)
            check_backup(bundle)
            _publish_file(bundle, destination)
    return destination


def _sanitize_restore(directory):
    with closing(sqlite3.connect(directory / "users.db")) as db, db:
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        tables = {
            row[0]
            for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in (
            "login_sessions",
            "password_reset_tokens",
            "registration_email_verifications",
            "registration_browser_bindings",
            "registration_mail_deliveries",
            "pending_registrations",
        ):
            if table in tables:
                db.execute("DELETE FROM " + table)
        db.execute("UPDATE user_email_verifications SET token_hash=NULL")
    with closing(sqlite3.connect(directory / "coach_conversations.db")) as db, db:
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute(
            "UPDATE coach_turns SET status='failed',completed_at=? WHERE status='pending'",
            (int(time()),),
        )
    for name in DATABASES:
        _database_ok(directory / name, name)


def restore_backup(archive, target):
    target = Path(target).expanduser().absolute()
    if target.exists() or target.is_symlink():
        raise BackupError("恢复只允许使用不存在的新目录，不覆盖已有目录。")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".coach-restore-", dir=target.parent
    ) as temporary:
        work = Path(temporary)
        summary = _extract_checked(archive, work)
        _sanitize_restore(work)
        # mkdir reserves a new destination; each link is also exclusive.
        target.mkdir()
        with data_directory_lock(target):
            incomplete = target / ".coach-restore-incomplete"
            incomplete.write_text("incomplete", encoding="ascii")
            for name in FILES:
                _publish_file(work / name, target / name)
            incomplete.unlink()
    return summary


def default_backup_path():
    return (
        ROOT
        / "data/coach-backups"
        / (
            "zhixing-"
            + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            + "-"
            + uuid4().hex[:8]
            + ".zip"
        )
    )
