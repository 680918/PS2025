from dataclasses import dataclass, field


@dataclass
class AssembledContext:
    conversation_context: list
    learning_continuity: dict
    memory_context: dict
    source_priority: list = field(
        default_factory=lambda: [
            "conversation",
            "learning_continuity",
            "memory",
        ]
    )
    source_budget: dict = field(
        default_factory=dict,
    )

    def ordered_sources(self):
        source_values = {
            "conversation": self.conversation_context,
            "learning_continuity": self.learning_continuity,
            "memory": self.memory_context,
        }

        return [
            (
                source,
                source_values[source],
            )
            for source in self.source_priority
        ]

    def budget_for(self, source):
        return self.source_budget.get(source)

    def preferred_source(self, sources):
        for source in self.source_priority:
            if source in sources:
                return source

        return None


def assemble_context(
    conversation_context,
    learning_continuity,
    memory_context,
    source_budget=None,
    source_priority=None,
):
    return AssembledContext(
        conversation_context=conversation_context,
        learning_continuity=learning_continuity,
        memory_context=memory_context,
        source_priority=(
            source_priority
            if source_priority is not None
            else [
                "conversation",
                "learning_continuity",
                "memory",
            ]
        ),
        source_budget=(source_budget if source_budget is not None else {}),
    )
