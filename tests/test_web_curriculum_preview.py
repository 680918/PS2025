from fastapi.testclient import TestClient

from api.app import create_app
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)
from learning.sqlite_curriculum_repository import (
    SQLiteLearningCurriculumRepository,
)


def test_web_curriculum_preview_should_render_topics_without_creating_journey(
    tmp_path,
):
    class FakeCurriculumGenerator:
        def generate(self, domain, goal):
            assert domain == "Python"
            assert goal == "能够独立编写简单程序"

            return [
                "Python变量",
                "Python条件判断",
                "Python函数",
            ]

    app = create_app(
        database_dir=tmp_path,
        curriculum_generator=FakeCurriculumGenerator(),
    )

    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    response = client.post(
        "/web/curriculums/preview",
        data={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    )

    assert response.status_code == 200

    assert "课程计划预览" in response.text
    assert "Python变量" in response.text
    assert "Python条件判断" in response.text
    assert "Python函数" in response.text

    journey_repository = SQLiteLearningJourneyRepository(tmp_path / "journeys.db")

    assert journey_repository.list_by_user(user["user_id"]) == []


def test_web_curriculum_preview_should_render_confirmation_form(
    tmp_path,
):
    class FakeCurriculumGenerator:
        def generate(self, domain, goal):
            return [
                "Python变量",
                "Python函数",
            ]

    app = create_app(
        database_dir=tmp_path,
        curriculum_generator=FakeCurriculumGenerator(),
    )

    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    response = client.post(
        "/web/curriculums/preview",
        data={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    )

    assert response.status_code == 200

    html = response.text

    assert '<form method="post" action="/web/journeys">' in html
    assert 'name="user_id"' in html
    assert f'value="{user["user_id"]}"' in html
    assert 'name="domain"' in html
    assert 'name="goal"' in html

    assert html.count('name="curriculum_topics"') == 2
    assert 'value="Python变量"' in html
    assert 'value="Python函数"' in html

    assert "确认创建学习旅程" in html


def test_web_confirmation_should_create_journey_with_previewed_curriculum(
    tmp_path,
):
    class FakeCurriculumGenerator:
        def generate(self, domain, goal):
            return [
                "Python变量",
                "Python条件判断",
                "Python函数",
            ]

    app = create_app(
        database_dir=tmp_path,
        curriculum_generator=FakeCurriculumGenerator(),
    )

    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    preview_response = client.post(
        "/web/curriculums/preview",
        data={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    )

    assert preview_response.status_code == 200

    journey_repository = SQLiteLearningJourneyRepository(tmp_path / "journeys.db")

    assert journey_repository.list_by_user(user["user_id"]) == []

    confirm_response = client.post(
        "/web/journeys",
        data={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "能够独立编写简单程序",
            "curriculum_topics": [
                "Python变量",
                "Python条件判断",
                "Python函数",
            ],
        },
    )

    assert confirm_response.status_code == 200

    journeys = journey_repository.list_by_user(user["user_id"])

    assert len(journeys) == 1

    curriculum_repository = SQLiteLearningCurriculumRepository(
        tmp_path / "curriculums.db"
    )

    curriculum = curriculum_repository.get_by_journey_id(journeys[0].journey_id)

    assert curriculum is not None

    assert [(item.position, item.topic) for item in curriculum.items] == [
        (1, "Python变量"),
        (2, "Python条件判断"),
        (3, "Python函数"),
    ]
