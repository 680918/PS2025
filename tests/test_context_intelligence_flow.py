from agent.context.source_selector import (
    select_context_sources,
)

from agent.context.runtime import (
    ContextRuntime,
)


class FakeProvider:
    def __init__(
        self,
        context,
    ):
        self.context = context

    def get_context(self):

        return self.context


def test_context_intelligence_should_select_and_assemble_context():

    query = "我为什么学不会Python？"

    selected_sources = select_context_sources(query)

    runtime = ContextRuntime(
        providers={
            "learning": FakeProvider(
                {
                    "topic": "Python",
                    "status": "learning",
                }
            ),
            "memory": FakeProvider({"history": "过去Python练习记录"}),
        }
    )

    context = runtime.build(selected_sources)

    assert "learning" in selected_sources

    assert "memory" in selected_sources

    assert context["learning"]["topic"] == "Python"

    assert context["memory"]["history"] == "过去Python练习记录"
