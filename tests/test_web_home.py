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


def test_home_page_should_render_registration_form(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200

    assert '<form method="post" action="/web/register">' in response.text
    assert 'name="name"' in response.text
    assert 'name="email"' in response.text
    assert "注册" in response.text
