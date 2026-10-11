from dataclasses import dataclass, field


@dataclass
class CoachContext:
    user_context: dict = field(default_factory=dict)
    learning_context: dict = field(default_factory=dict)
    memory_context: list = field(default_factory=list)
