from fastapi.testclient import TestClient

from api.app import create_app


def test_home_page_should_render_learning_coach_title(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "AI Learning Coach" in response.text


def test_home_page_should_offer_registration_and_existing_user_login(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200

    assert 'href="/web/register"' in response.text
    assert 'href="/web/login"' in response.text
    assert "我已有账户" in response.text
    assert "有问题，慢慢聊。" in response.text
    assert '<form method="post" action="/web/register">' not in response.text
