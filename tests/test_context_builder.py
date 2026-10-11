from coach.context_builder import (
    build_coach_context,
)


class FakeUser:
    user_id = "u1"
    name = "Test"
    email = "test@test.com"


class FakeUserRepository:
    def get_by_id(self, user_id):
        return FakeUser()


class FakeJourney:
    domain = "AI Agent"
    goal = "Build Agent"
    status = "active"


class FakeJourneyRepository:
    def get_by_id(self, journey_id):
        return FakeJourney()


class FakeMemoryService:
    def get_context(self):
        return {"learning": ["Tool Calling"]}


def test_build_coach_context():

    context = build_coach_context(
        user_id="u1",
        user_message="continue learning",
        user_repository=FakeUserRepository(),
        journey_repository=FakeJourneyRepository(),
        memory_service=FakeMemoryService(),
        journey_id="j1",
    )

    assert context.user_context["name"] == "Test"

    assert context.learning_context["domain"] == "AI Agent"

    assert "learning" in context.memory_context
