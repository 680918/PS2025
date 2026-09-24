from fastapi.testclient import TestClient

from api.app import create_app


def test_web_register_should_create_user_and_render_success(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.post(
        "/web/register",
        data={
            "name": "张三",
            "email": "ZHANGSAN@EXAMPLE.COM",
        },
    )

    assert response.status_code == 200

    assert "注册成功" in response.text
    assert "张三" in response.text
    assert "zhangsan@example.com" in response.text


def test_web_register_should_render_curriculum_preview_form(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.post(
        "/web/register",
        data={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    )

    assert response.status_code == 200

    assert '<form method="post" action="/web/curriculums/preview">' in response.text

    assert 'name="user_id"' in response.text
    assert 'name="domain"' in response.text
    assert 'name="goal"' in response.text

    assert "生成课程计划" in response.text


def test_web_register_should_include_user_id_in_journey_form(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    response = client.post(
        "/web/register",
        data={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    )

    assert response.status_code == 200

    assert 'name="user_id"' in response.text
    assert 'type="hidden"' in response.text
