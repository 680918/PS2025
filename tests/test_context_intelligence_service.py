from agent.context.service import (
    ContextIntelligenceService,
)


class FakeProvider:
    def __init__(self, value):
        self.value = value

    def get_context(self):
        return self.value


def test_context_intelligence_service_should_build_context():

    service = ContextIntelligenceService(
        providers={
            "learning": FakeProvider({"topic": "Python"}),
            "memory": FakeProvider({"history": "old learning"}),
        }
    )

    result = service.build_context("我为什么学不会Python？")

    assert "learning" in result["selected_sources"]

    assert "memory" in result["selected_sources"]

    assert result["assembled_context"]["learning"]["topic"] == "Python"
