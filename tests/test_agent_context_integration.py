from agent.state import AgentState

from agent.context.runtime import (
    ContextRuntime,
)


class FakeProvider:
    def __init__(
        self,
        value,
    ):
        self.value = value

    def get_context(self):

        return self.value


def test_agent_should_store_assembled_context():

    state = AgentState("我为什么学不会Python？")

    runtime = ContextRuntime(
        providers={
            "learning": FakeProvider({"topic": "Python"}),
            "memory": FakeProvider({"history": "过去学习记录"}),
        }
    )

    context = runtime.build(
        [
            "learning",
            "memory",
        ]
    )

    state.set_assembled_context(context)

    assert state.assembled_context is not None

    assert state.assembled_context["learning"]["topic"] == "Python"

    assert state.assembled_context["memory"]["history"] == "过去学习记录"
