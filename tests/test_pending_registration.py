import re
import sqlite3
import smtplib
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

from api.app import create_app
from security.auth import initialize_user_password, verify_user_password
from security.email_verification import (
    confirm_email_verification,
    issue_email_verification,
)
from security.passwords import verify_password
from security.pending_registration import (
    PendingRegistrationUnavailable,
    begin_pending_registration,
    get_pending_registration,
)
from user.model import User
from user.sqlite_repository import SQLiteUserRepository


NOW = datetime(2026, 10, 16, 8, 0, tzinfo=timezone.utc)
PASSWORD = " a quiet registration phrase "


@pytest.fixture(autouse=True)
def no_mail(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("pending foundation must not contact SMTP")

    monkeypatch.setattr(smtplib, "SMTP", forbidden)
    monkeypatch.setattr(smtplib, "SMTP_SSL", forbidden)


@pytest.fixture
def repository(tmp_path):
    return SQLiteUserRepository(tmp_path / "users.db")


def begin(repository, **changes):
    fields = {
        "name": "测试成长者",
        "email": "learner@example.com",
        "password": PASSWORD,
        "now": NOW,
    }
    fields.update(changes)
    return begin_pending_registration(repository, **fields)


def test_draft_stores_only_hash_and_does_not_create_user_credentials(
    repository, capsys
):
    receipt = begin(repository, email="  Learner@Example.COM  ")
    record = get_pending_registration(repository, receipt.request_id, now=NOW)
    assert receipt.expires_at == NOW + timedelta(hours=1)
    assert record.created_at == NOW
    assert record.email == "learner@example.com"
    assert record.name == "测试成长者"
    assert record.password_hash.startswith("$argon2id$")
    assert verify_password(PASSWORD, record.password_hash)
    assert not verify_password(PASSWORD.strip(), record.password_hash)
    assert repository.get_by_email(record.email) is None
    assert repository.get_by_id(receipt.request_id) is None
    assert repository.get_password_hash(receipt.request_id) is None
    assert not verify_user_password(repository, receipt.request_id, PASSWORD)
    assert confirm_email_verification(repository, receipt.request_id, now=NOW) is None
    assert PASSWORD.encode() not in repository.database_path.read_bytes()
    for value in (
        record.email,
        record.name,
        record.password_hash,
        receipt.request_id,
        PASSWORD,
    ):
        assert value not in repr(record)
        assert value not in repr(receipt)
    assert capsys.readouterr().out == ""


def test_pending_registration_survives_restart_without_extending_expiry(repository):
    receipt = begin(repository, name="")
    restored = SQLiteUserRepository(repository.database_path)
    record = get_pending_registration(
        restored, receipt.request_id, now=NOW + timedelta(minutes=10)
    )
    assert record.name == "成长者"
    assert record.expires_at == receipt.expires_at
    assert record.created_at == NOW
    assert verify_password(PASSWORD, record.password_hash)


@pytest.mark.parametrize(
    "seconds,active",
    [(-1, False), (0, True), (3599, True), (3600, False), (3601, False)],
)
def test_time_boundaries_and_expired_record_cleanup(repository, seconds, active):
    receipt = begin(repository)
    record = get_pending_registration(
        repository, receipt.request_id, now=NOW + timedelta(seconds=seconds)
    )
    assert (record is not None) is active
    with sqlite3.connect(repository.database_path) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM pending_registrations"
        ).fetchone()[0]
    assert count == (0 if seconds >= 3600 else 1)
    if seconds < 0:
        assert (
            get_pending_registration(repository, receipt.request_id, now=NOW)
            is not None
        )


def test_active_duplicate_cannot_replace_password_name_id_or_expiry(repository):
    receipt = begin(repository)
    before = get_pending_registration(repository, receipt.request_id, now=NOW)
    with pytest.raises(PendingRegistrationUnavailable) as caught:
        begin(
            repository,
            email="LEARNER@EXAMPLE.COM",
            name="不同的称呼",
            password="a different registration password",
            now=NOW + timedelta(minutes=2),
        )
    assert "learner" not in str(caught.value)
    after = get_pending_registration(repository, receipt.request_id, now=NOW)
    assert after == before
    assert verify_password(PASSWORD, after.password_hash)
    assert not verify_password("a different registration password", after.password_hash)


def test_expired_draft_can_be_replaced_with_new_id_and_hash(repository):
    first = begin(repository)
    later = NOW + timedelta(hours=1)
    second = begin(repository, password="a different registration password", now=later)
    assert second.request_id != first.request_id
    assert get_pending_registration(repository, first.request_id, now=later) is None
    record = get_pending_registration(repository, second.request_id, now=later)
    assert verify_password("a different registration password", record.password_hash)
    assert not verify_password(PASSWORD, record.password_hash)
    assert repository.get_by_email(record.email) is None


def test_new_draft_lazily_removes_other_expired_drafts(repository):
    first = begin(repository)
    second = begin(repository, email="other@example.com", now=NOW + timedelta(hours=1))
    with sqlite3.connect(repository.database_path) as connection:
        assert connection.execute(
            "SELECT request_id FROM pending_registrations"
        ).fetchall() == [(second.request_id,)]
    assert first.request_id != second.request_id


@pytest.mark.parametrize(
    "old_email", ["learner@example.com", "Learner@Example.COM", " learner@example.com "]
)
def test_existing_user_password_and_verification_cannot_be_changed(
    repository, old_email
):
    user = User(name="原有用户", email=old_email)
    repository.save(user)
    initialize_user_password(repository, user.user_id, PASSWORD)
    token_message = issue_email_verification(
        repository, user.user_id, "https://coach.example.com/web/verify-email", now=NOW
    )
    from urllib.parse import parse_qs, urlsplit

    token = parse_qs(urlsplit(token_message.activation_url).query)["token"][0]
    assert confirm_email_verification(repository, token, now=NOW) == user.user_id
    original_hash = repository.get_password_hash(user.user_id)
    with pytest.raises(PendingRegistrationUnavailable):
        begin(repository, password="a different registration password")
    assert repository.get_by_id(user.user_id) == user
    assert repository.get_password_hash(user.user_id) == original_hash
    assert repository.is_email_verified(user.user_id)
    assert verify_user_password(repository, user.user_id, PASSWORD)


def test_draft_becomes_unavailable_if_account_is_created_by_another_flow(repository):
    receipt = begin(repository)
    user = User(name="已有账户", email="Learner@Example.COM")
    repository.save(user)
    assert get_pending_registration(repository, receipt.request_id, now=NOW) is None
    assert repository.get_by_id(user.user_id) == user
    assert repository.get_password_hash(user.user_id) is None
    with sqlite3.connect(repository.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM pending_registrations").fetchone()[
                0
            ]
            == 0
        )


def test_competing_submissions_have_only_one_winner_without_overwrite(repository):
    barrier = Barrier(2)

    def submit(index):
        barrier.wait(timeout=10)
        try:
            receipt = begin(
                repository,
                name=f"测试{index}",
                password=f"a registration phrase for {index}",
            )
            return index, receipt
        except PendingRegistrationUnavailable:
            return index, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(submit, [1, 2]))
    winners = [(index, receipt) for index, receipt in outcomes if receipt is not None]
    assert len(winners) == 1
    index, receipt = winners[0]
    record = get_pending_registration(repository, receipt.request_id, now=NOW)
    assert record.name == f"测试{index}"
    assert verify_password(f"a registration phrase for {index}", record.password_hash)
    assert not verify_password(
        f"a registration phrase for {3 - index}", record.password_hash
    )
    with sqlite3.connect(repository.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM pending_registrations").fetchone()[
                0
            ]
            == 1
        )


@pytest.mark.parametrize(
    "fields",
    [
        {"email": "bad"},
        {"email": None},
        {"name": "名" * 41},
        {"name": []},
        {"password": "short"},
        {"password": " " * 15},
        {"password": "x" * 129},
        {"password": None},
    ],
)
def test_invalid_details_are_rejected_before_hashing_or_writing(
    repository, monkeypatch, fields
):
    import security.pending_registration as service

    def should_not_hash(*args):
        raise AssertionError("invalid details must not be hashed")

    monkeypatch.setattr(service, "hash_password", should_not_hash)
    with pytest.raises(ValueError, match="invalid registration details"):
        begin(repository, **fields)
    with sqlite3.connect(repository.database_path) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM pending_registrations").fetchone()[
                0
            ]
            == 0
        )


@pytest.mark.parametrize(
    "request_id", [None, 12, "", "unknown", "registration_" + "g" * 32, "' OR 1=1 --"]
)
def test_invalid_identifiers_do_not_read_or_authenticate(repository, request_id):
    assert get_pending_registration(repository, request_id, now=NOW) is None


def test_naive_time_is_not_assumed_to_be_local(repository):
    with pytest.raises(ValueError, match="timezone"):
        begin(repository, now=datetime(2026, 10, 16))
    receipt = begin(repository)
    with pytest.raises(ValueError, match="timezone"):
        get_pending_registration(
            repository, receipt.request_id, now=datetime(2026, 10, 16)
        )
    china = NOW.astimezone(timezone(timedelta(hours=8)))
    assert (
        get_pending_registration(repository, receipt.request_id, now=china).created_at
        == NOW
    )


def test_plaintext_is_rejected_by_repository_and_schema(repository):
    values = (
        "registration_" + "a" * 32,
        "测试",
        "learner@example.com",
        PASSWORD,
        int(NOW.timestamp()),
        int(NOW.timestamp()) + 3600,
    )
    with pytest.raises(ValueError, match="Argon2id"):
        repository.save_pending_registration(
            request_id=values[0],
            name=values[1],
            email=values[2],
            password_hash=values[3],
            created_at=values[4],
            expires_at=values[5],
        )
    with sqlite3.connect(repository.database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO pending_registrations VALUES (?, ?, ?, ?, ?, ?)", values
            )


def test_legacy_database_and_learning_files_are_preserved(tmp_path):
    database = tmp_path / "users.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE users (user_id TEXT PRIMARY KEY,name TEXT NOT NULL,email TEXT NOT NULL UNIQUE)"
        )
        connection.execute(
            "INSERT INTO users VALUES ('old-user','旧用户','old@example.com')"
        )
    notes = tmp_path / "learning-notes.md"
    notes.write_text("已有的成长记录", encoding="utf-8")
    repo = SQLiteUserRepository(database)
    begin(repo)
    assert repo.get_by_id("old-user").email == "old@example.com"
    assert repo.get_password_hash("old-user") is None
    assert not repo.is_email_verified("old-user")
    assert notes.read_text(encoding="utf-8") == "已有的成长记录"


def test_web_form_remains_read_only_and_cannot_replace_internal_draft(
    repository, tmp_path
):
    # Use the current clock because this is a web request, not a supplied time.
    receipt = begin(repository, now=datetime.now(timezone.utc))
    before = get_pending_registration(repository, receipt.request_id)
    app = create_app(
        tmp_path,
        curriculum_generator=None,
        completion_commentary_generator=None,
        learning_feedback_extractor=None,
    )
    with TestClient(app) as client:
        form = client.get("/web/register")
        csrf = re.search(r'name="csrf" value="([A-Za-z0-9_-]{43})"', form.text).group(1)
        response = client.post(
            "/web/auth/register",
            data={
                "email": "learner@example.com",
                "password": "a different registration password",
                "csrf": csrf,
            },
        )
        assert response.status_code == 200
        assert "无需等待邮件" in response.text
        assert "set-cookie" not in response.headers
        assert (
            client.post(
                "/web/auth/login",
                data={"email": "learner@example.com", "password": PASSWORD},
            ).status_code
            == 503
        )
    assert get_pending_registration(repository, receipt.request_id) == before
    assert repository.get_by_email("learner@example.com") is None
