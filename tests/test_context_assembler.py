from agent.context.assembler import (
    assemble_context,
)


def test_assembler_should_combine_multiple_context_sources():

    contexts = {
        "memory": "过去学习记录",
        "learning": "当前学习状态",
    }

    result = assemble_context(contexts)

    assert "memory" in result

    assert "learning" in result

    assert result["memory"] == "过去学习记录"
