from coach.knowledge.context_adapter import (
    adapt_knowledge_context,
)


def test_adapter_should_convert_artifact_context_to_agent_context():

    artifact_context = """
主题:
Memory Retrieval

内容:
关于记忆检索的方法
"""

    result = adapt_knowledge_context(artifact_context)

    assert result["type"] == "knowledge"

    assert "Memory Retrieval" in result["content"]
