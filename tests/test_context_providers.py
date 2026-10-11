from coach.context_providers.user_context_provider import (
    build_user_context,
)

from coach.context_providers.learning_context_provider import (
    build_learning_context,
)

from coach.context_providers.memory_context_provider import (
    build_memory_context,
)


class FakeUser:
    user_id = "user-1"
    name = "Test User"
    email = "test@example.com"


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
        return {"learning": [{"content": "Tool Calling completed"}]}


def test_user_context_provider():
    context = build_user_context(
        FakeUserRepository(),
        "user-1",
    )

    assert context == {
        "user_id": "user-1",
        "name": "Test User",
        "email": "test@example.com",
    }


def test_learning_context_provider():
    context = build_learning_context(
        FakeJourneyRepository(),
        "journey-1",
    )

    assert context["domain"] == "AI Agent"


def test_memory_context_provider():
    context = build_memory_context(
        FakeMemoryService(),
        "hello",
    )

    assert "learning" in context


def test_user_context_should_return_empty_when_user_missing():
    class EmptyRepository:
        def get_by_id(self, user_id):
            return None

    context = build_user_context(
        EmptyRepository(),
        "missing",
    )

    assert context == {}


def test_learning_context_should_return_empty_when_journey_missing():
    class EmptyRepository:
        def get_by_id(self, journey_id):
            return None

    context = build_learning_context(
        EmptyRepository(),
        "missing",
    )

    assert context == {}


def test_memory_context_should_return_empty_when_service_missing():

    context = build_memory_context(
        None,
        "hello",
    )

    assert context == {}
