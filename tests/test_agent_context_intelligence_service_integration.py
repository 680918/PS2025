from agent.state import AgentState

from agent.context.service import (
    ContextIntelligenceService,
)


class FakeProvider:
    def __init__(self, value):
        self.value = value

    def get_context(self):
        return self.value


def test_agent_should_store_context_intelligence_result():

    state = AgentState("我为什么学不会Python？")

    service = ContextIntelligenceService(
        providers={
            "learning": FakeProvider({"topic": "Python"}),
            "memory": FakeProvider({"history": "previous"}),
        }
    )

    result = service.build_context(state.user_message)

    state.set_context_intelligence_result(result)

    assert state.context_intelligence_result is not None

    assert "learning" in result["selected_sources"]

    assert "memory" in result["selected_sources"]
