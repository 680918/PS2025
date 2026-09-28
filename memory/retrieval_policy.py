import json
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryRetrievalPolicy:
    name: str

    def should_include(
        self,
        memory,
        learning_domain=None,
    ):
        return True


@dataclass(frozen=True)
class JourneyCompletionPolicy(MemoryRetrievalPolicy):
    def should_include(
        self,
        memory,
        learning_domain=None,
    ):
        if learning_domain is None:
            return True

        try:
            content = json.loads(memory["content"])
        except (json.JSONDecodeError, TypeError, KeyError):
            return False

        return content.get("domain") == learning_domain


def get_memory_policy(memory_key):
    memory_type = memory_key.split(":", 1)[0]

    if memory_type == "journey_completion":
        return JourneyCompletionPolicy(
            name=memory_type,
        )

    return MemoryRetrievalPolicy(
        name=memory_type,
    )
