import sqlite3
import pytest

from user.model import User
from user.sqlite_repository import (
    SQLiteUserRepository,
)


def test_sqlite_user_repository_should_persist_and_restore_user(
    tmp_path,
):
    database_path = tmp_path / "users.db"

    repository = SQLiteUserRepository(database_path)

    user = User(
        name="张三",
        email="zhangsan@example.com",
    )

    repository.save(user)

    restored_repository = SQLiteUserRepository(database_path)

    restored_user = restored_repository.get_by_id(user.user_id)

    assert restored_user is not None
    assert restored_user.user_id == user.user_id
    assert restored_user.name == "张三"
    assert restored_user.email == "zhangsan@example.com"


def test_sqlite_user_repository_should_get_user_by_email(
    tmp_path,
):
    database_path = tmp_path / "users.db"

    repository = SQLiteUserRepository(database_path)

    user = User(
        name="张三",
        email="zhangsan@example.com",
    )

    repository.save(user)

    restored_user = repository.get_by_email("zhangsan@example.com")

    assert restored_user is not None
    assert restored_user.user_id == user.user_id
    assert restored_user.name == "张三"


def test_sqlite_user_repository_should_reject_duplicate_email(
    tmp_path,
):
    database_path = tmp_path / "users.db"

    repository = SQLiteUserRepository(database_path)

    first_user = User(
        name="张三",
        email="zhangsan@example.com",
    )

    second_user = User(
        name="李四",
        email="zhangsan@example.com",
    )

    repository.save(first_user)

    with pytest.raises(sqlite3.IntegrityError):
        repository.save(second_user)
