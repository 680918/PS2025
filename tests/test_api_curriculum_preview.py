import learning.llm_curriculum_generator as llm_curriculum_generator

from fastapi.testclient import TestClient
from api.app import create_app
from learning.sqlite_journey_repository import (
    SQLiteLearningJourneyRepository,
)


def test_post_curriculum_preview_should_return_topics_without_creating_journey(
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

    response = client.post(
        "/curriculums/preview",
        json={
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "curriculum_topics": [
            "Python变量",
            "Python条件判断",
            "Python函数",
        ]
    }

    journey_repository = SQLiteLearningJourneyRepository(tmp_path / "journeys.db")

    assert journey_repository.list_by_user("user_001") == []


def test_post_curriculum_preview_should_return_503_without_generator(
    tmp_path,
):
    app = create_app(
        database_dir=tmp_path,
        curriculum_generator=None,
    )
    client = TestClient(app)

    response = client.post(
        "/curriculums/preview",
        json={
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == ("curriculum generator is not configured")


def test_post_curriculum_preview_should_reject_invalid_generated_topics(
    tmp_path,
):
    class FakeCurriculumGenerator:
        def generate(self, domain, goal):
            return [
                "Python变量",
                "   ",
            ]

    app = create_app(
        database_dir=tmp_path,
        curriculum_generator=FakeCurriculumGenerator(),
    )
    client = TestClient(app)

    response = client.post(
        "/curriculums/preview",
        json={
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "curriculum topics must not contain blank strings"
    )


def test_post_curriculum_preview_should_use_default_llm_generator(
    tmp_path,
    monkeypatch,
):
    def fake_call_llm(system_prompt, user_message):
        return {
            "status": "success",
            "content": """
            {
                "curriculum_topics": [
                    "Python变量",
                    "Python条件判断",
                    "Python函数"
                ]
            }
            """,
        }

    monkeypatch.setattr(
        llm_curriculum_generator,
        "call_llm",
        fake_call_llm,
    )

    app = create_app(
        database_dir=tmp_path,
    )

    client = TestClient(app)

    response = client.post(
        "/curriculums/preview",
        json={
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "curriculum_topics": [
            "Python变量",
            "Python条件判断",
            "Python函数",
        ]
    }


def test_post_curriculum_preview_should_return_503_when_llm_generation_fails(
    tmp_path,
    monkeypatch,
):
    def fake_call_llm(system_prompt, user_message):
        return {
            "status": "error",
            "error_type": "llm_timeout",
            "message": "request timed out",
            "content": None,
        }

    monkeypatch.setattr(
        llm_curriculum_generator,
        "call_llm",
        fake_call_llm,
    )

    app = create_app(
        database_dir=tmp_path,
    )

    client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = client.post(
        "/curriculums/preview",
        json={
            "domain": "Python",
            "goal": "能够独立编写简单程序",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == ("curriculum generation is unavailable")
