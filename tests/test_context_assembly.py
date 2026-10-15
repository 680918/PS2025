from agent.context_assembly import (
    assemble_context,
)


def test_assemble_context_should_keep_context_sources_separate():
    conversation_context = [
        {
            "role": "user",
            "content": "那第二种呢？",
        }
    ]

    learning_continuity = {
        "topic": "Tool Calling",
        "understanding_score": 80,
    }

    memory_context = {
        "learning": [
            {
                "memory_key": "learning_feedback:tool-calling",
                "content": "用户已经基本理解 Tool Calling",
            }
        ]
    }

    assembled = assemble_context(
        conversation_context=conversation_context,
        learning_continuity=learning_continuity,
        memory_context=memory_context,
    )

    assert assembled.conversation_context == conversation_context
    assert assembled.learning_continuity == learning_continuity
    assert assembled.memory_context == memory_context


def test_assembled_context_should_expose_source_priority():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    assert assembled.source_priority == [
        "conversation",
        "learning_continuity",
        "memory",
    ]


def test_assembled_context_should_return_sources_in_priority_order():
    conversation_context = [
        {
            "role": "user",
            "content": "那第二种呢？",
        }
    ]

    learning_continuity = {
        "topic": "Tool Calling",
    }

    memory_context = {
        "learning": [
            {
                "memory_key": "learning_feedback:tool-calling",
            }
        ]
    }

    assembled = assemble_context(
        conversation_context=conversation_context,
        learning_continuity=learning_continuity,
        memory_context=memory_context,
    )

    assert assembled.ordered_sources() == [
        (
            "conversation",
            conversation_context,
        ),
        (
            "learning_continuity",
            learning_continuity,
        ),
        (
            "memory",
            memory_context,
        ),
    ]


def test_assembled_context_should_expose_source_budget():
    source_budget = {
        "conversation": 10,
        "learning_continuity": 1,
        "memory": 5,
    }

    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
        source_budget=source_budget,
    )

    assert assembled.source_budget == source_budget


def test_assembled_context_should_return_budget_for_source():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
        source_budget={
            "conversation": 10,
            "learning_continuity": 1,
            "memory": 5,
        },
    )

    assert assembled.budget_for("conversation") == 10
    assert assembled.budget_for("learning_continuity") == 1
    assert assembled.budget_for("memory") == 5


def test_assembled_context_should_choose_higher_priority_source():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
    )

    assert (
        assembled.preferred_source(
            [
                "memory",
                "conversation",
            ]
        )
        == "conversation"
    )


def test_assemble_context_should_allow_custom_source_priority():
    assembled = assemble_context(
        conversation_context=[],
        learning_continuity={},
        memory_context={},
        source_priority=[
            "learning_continuity",
            "conversation",
            "memory",
        ],
    )

    assert assembled.source_priority == [
        "learning_continuity",
        "conversation",
        "memory",
    ]

    assert (
        assembled.preferred_source(
            [
                "conversation",
                "learning_continuity",
            ]
        )
        == "learning_continuity"
    )


def test_preferred_source_should_not_mutate_context():
    conversation = [{"role": "user", "content": "学习 Memory"}]

    learning_continuity = {
        "topic": "Memory",
    }

    memory_context = {
        "learning": [
            {
                "memory_key": "old-direction",
                "content": "继续学习 Tool Calling",
            }
        ]
    }

    assembled = assemble_context(
        conversation_context=conversation,
        learning_continuity=learning_continuity,
        memory_context=memory_context,
    )

    preferred = assembled.preferred_source(
        [
            "learning_continuity",
            "memory",
        ]
    )

    assert preferred == "learning_continuity"

    assert assembled.learning_continuity == learning_continuity
    assert assembled.memory_context == memory_context
