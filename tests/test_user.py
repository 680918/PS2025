from user.model import User


def test_user_should_store_basic_identity():
    user = User(
        name="张三",
        email="zhangsan@example.com",
    )

    assert user.name == "张三"
    assert user.email == "zhangsan@example.com"
    assert user.user_id
