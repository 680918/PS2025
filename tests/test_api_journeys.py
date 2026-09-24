from fastapi.testclient import TestClient
from learning.sqlite_curriculum_repository import (
    SQLiteLearningCurriculumRepository,
)
from api.app import create_app


def test_post_journeys_should_create_learning_journey(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)

    client = TestClient(app)

    user_response = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    )

    user = user_response.json()

    response = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "英语",
            "goal": "6个月达到日常交流",
        },
    )

    assert response.status_code == 201

    data = response.json()

    assert data["user_id"] == user["user_id"]

    assert data["domain"] == "英语"

    assert data["goal"] == "6个月达到日常交流"

    curriculum_repository = SQLiteLearningCurriculumRepository(
        tmp_path / "curriculums.db"
    )

    curriculum = curriculum_repository.get_by_journey_id(data["journey_id"])

    assert curriculum is None


def test_post_journeys_should_initialize_explicit_curriculum(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    response = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "掌握 Python 编程",
            "curriculum_topics": [
                "Python变量",
                "Python条件判断",
                "Python函数",
            ],
        },
    )

    assert response.status_code == 201

    journey_id = response.json()["journey_id"]

    restored_repository = SQLiteLearningCurriculumRepository(
        tmp_path / "curriculums.db"
    )

    curriculum = restored_repository.get_by_journey_id(journey_id)

    assert curriculum is not None
    assert curriculum.journey_id == journey_id

    assert [(item.position, item.topic) for item in curriculum.items] == [
        (1, "Python变量"),
        (2, "Python条件判断"),
        (3, "Python函数"),
    ]


def test_post_journeys_should_preserve_explicit_empty_curriculum(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    response = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "掌握 Python 编程",
            "curriculum_topics": [],
        },
    )

    assert response.status_code == 201

    journey_id = response.json()["journey_id"]

    curriculum_repository = SQLiteLearningCurriculumRepository(
        tmp_path / "curriculums.db"
    )

    curriculum = curriculum_repository.get_by_journey_id(journey_id)

    assert curriculum is not None
    assert curriculum.journey_id == journey_id
    assert curriculum.items == []


def test_post_journeys_should_reject_invalid_curriculum_topics(
    tmp_path,
):
    app = create_app(database_dir=tmp_path)
    client = TestClient(app)

    user = client.post(
        "/users",
        json={
            "name": "张三",
            "email": "zhangsan@example.com",
        },
    ).json()

    response = client.post(
        "/journeys",
        json={
            "user_id": user["user_id"],
            "domain": "Python",
            "goal": "掌握 Python 编程",
            "curriculum_topics": [
                "Python变量",
                123,
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == ("curriculum_topics must be a list of strings")
