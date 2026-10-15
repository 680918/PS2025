from agent.context_assembly import assemble_context
from agent.context_assembly_prompt import (
    format_assembled_context,
    format_assembled_context_policy,
)


def test_format_assembled_context_should_follow_source_priority():
    assembled = assemble_context(
        conversation_context=[
            {
                "role": "user",
                "content": "那第二种呢？",
            }
        ],
        learning_continuity={
            "topic": "Tool Calling",
        },
        memory_context={
            "learning": [
                {
                    "memory_key": "learning_feedback:tool-calling",
                    "content": "用户已经基本理解 Tool Calling",
                }
            ]
        },
        source_priority=[
            "conversation",
            "learning_continuity",
            "memory",
        ],
    )

    formatted = format_assembled_context(
        assembled,
    )

    conversation_position = formatted.index("Conversation Context")
    learning_position = formatted.index("Learning Continuity")
    memory_position = formatted.index("Memory Context")

    assert conversation_position < learning_position < memory_position


def test_format_assembled_context_policy_should_follow_source_priority():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
        source_priority=[
            "conversation",
            "learning_continuity",
            "memory",
        ],
    )

    policy = format_assembled_context_policy(
        assembled,
    )

    assert "conversation > learning_continuity > memory" in policy


def test_format_assembled_context_policy_should_include_context_usage_rules():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    policy = format_assembled_context_policy(
        assembled,
    )

    assert "当前用户输入优先于所有已装配上下文" in policy

    assert "Conversation Context" in policy
    assert "最近连续对话" in policy
    assert "不等同于长期记忆" in policy

    assert "Learning Continuity" in policy
    assert "current session" in policy
    assert "previous session" in policy

    assert "Memory Context" in policy
    assert "不得根据记忆推测新的用户事实" in policy


def test_format_assembled_context_policy_should_preserve_learning_continuity_semantics():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    policy = format_assembled_context_policy(
        assembled,
    )

    assert "has_current_session" in policy
    assert "has_previous_session" in policy
    assert "current_next_step" in policy
    assert "previous session" in policy
    assert "当前用户输入" in policy


def test_format_assembled_context_policy_should_preserve_memory_safety_rules():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    policy = format_assembled_context_policy(
        assembled,
    )

    assert "只能使用记忆中明确存在的信息" in policy
    assert "不得根据记忆推测新的用户事实" in policy
    assert "Memory JSON" in policy
