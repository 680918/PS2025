from agent.context.runtime import (
    ContextRuntime,
)


class FakeProvider:
    def __init__(self, value):
        self.value = value

    def get_context(self):
        return self.value


def test_context_runtime_should_collect_selected_contexts():

    runtime = ContextRuntime(
        providers={
            "learning": FakeProvider({"topic": "Python"}),
            "memory": FakeProvider({"history": "previous"}),
        }
    )

    result = runtime.build(
        [
            "learning",
            "memory",
        ]
    )

    assert result["learning"]["topic"] == "Python"

    assert result["memory"]["history"] == "previous"
