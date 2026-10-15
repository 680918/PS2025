from coach.context_providers.knowledge_context_provider import (
    build_knowledge_context,
)


class FakeArtifact:
    topic = "Memory Retrieval"

    content = "关于Memory Retrieval的学习教程"


class FakeRepository:
    def list_all(self):

        return [FakeArtifact()]


def test_knowledge_context_provider_should_build_context():

    context = build_knowledge_context(
        FakeRepository(),
        "Memory Retrieval",
    )

    assert "knowledge" in context

    assert context["knowledge"][0]["topic"] == "Memory Retrieval"

    assert context["knowledge"][0]["content"] == "关于Memory Retrieval的学习教程"
