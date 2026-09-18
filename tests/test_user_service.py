import pytest

from user.model import User
from user.service import register_user


def test_register_user_should_create_and_save_user():
    class FakeRepository:
        def __init__(self):
            self.saved_users = []

        def get_by_email(self, email):
            return None

        def save(self, user):
            self.saved_users.append(user)

    repository = FakeRepository()

    user = register_user(
        repository=repository,
        name="张三",
        email="zhangsan@example.com",
    )

    assert user.name == "张三"
    assert user.email == "zhangsan@example.com"
    assert user.user_id
    assert repository.saved_users == [user]


def test_register_user_should_reject_duplicate_email():
    existing_user = User(
        name="张三",
        email="zhangsan@example.com",
    )

    class FakeRepository:
        def get_by_email(self, email):
            return existing_user

        def save(self, user):
            raise AssertionError("duplicate user should not be saved")

    repository = FakeRepository()

    with pytest.raises(
        ValueError,
        match="email already registered",
    ):
        register_user(
            repository=repository,
            name="李四",
            email="zhangsan@example.com",
        )


def test_register_user_should_normalize_email():
    class FakeRepository:
        def __init__(self):
            self.saved_users = []
            self.queried_email = None

        def get_by_email(self, email):
            self.queried_email = email
            return None

        def save(self, user):
            self.saved_users.append(user)

    repository = FakeRepository()

    user = register_user(
        repository=repository,
        name="张三",
        email="  ZHANGSAN@EXAMPLE.COM  ",
    )

    assert repository.queried_email == "zhangsan@example.com"

    assert user.email == "zhangsan@example.com"


def test_register_user_should_reject_empty_email():
    class FakeRepository:
        def get_by_email(self, email):
            return None

        def save(self, user):
            raise AssertionError("invalid user should not be saved")

    repository = FakeRepository()

    with pytest.raises(
        ValueError,
        match="email is required",
    ):
        register_user(
            repository=repository,
            name="张三",
            email="   ",
        )


def test_register_user_should_reject_invalid_email():
    class FakeRepository:
        def get_by_email(self, email):
            return None

        def save(self, user):
            raise AssertionError("invalid user should not be saved")

    repository = FakeRepository()

    with pytest.raises(
        ValueError,
        match="invalid email",
    ):
        register_user(
            repository=repository,
            name="张三",
            email="zhangsan-example.com",
        )
