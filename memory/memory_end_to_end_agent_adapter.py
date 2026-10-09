from copy import deepcopy


_MEMORY_TYPES = (
    "profile",
    "skill",
    "learning",
    "project",
    "experience",
)


class StaticMemoryService:
    def __init__(
        self,
        memory_context,
    ):
        self._memory_context = deepcopy(memory_context)

    def get_context(self):
        return deepcopy(self._memory_context)


def _empty_runtime_memory_context():
    return {memory_type: [] for memory_type in _MEMORY_TYPES}


def normalize_runtime_memory_context(
    memory_context,
):
    if memory_context is None:
        memory_context = []

    if isinstance(
        memory_context,
        dict,
    ):
        normalized = _empty_runtime_memory_context()

        for memory_type in _MEMORY_TYPES:
            memories = memory_context.get(
                memory_type,
                [],
            )

            if not isinstance(
                memories,
                list,
            ):
                raise ValueError("runtime memory type must contain a list")

            normalized[memory_type] = deepcopy(memories)

        return normalized

    if not isinstance(
        memory_context,
        list,
    ):
        raise ValueError("memory_context must be a list or dict")

    normalized = _empty_runtime_memory_context()

    for memory in memory_context:
        if not isinstance(
            memory,
            dict,
        ):
            raise ValueError("memory must be a dict")

        memory_key = memory.get(
            "memory_key",
            "",
        )

        if (
            not isinstance(
                memory_key,
                str,
            )
            or ":" not in memory_key
        ):
            raise ValueError("memory_key must include a memory type prefix")

        memory_type = memory_key.split(
            ":",
            1,
        )[0]

        if memory_type not in (_MEMORY_TYPES):
            raise ValueError(f"unsupported memory type: {memory_type}")

        normalized[memory_type].append(deepcopy(memory))

    return normalized


def run_real_agent_for_memory_evaluation(
    *,
    query,
    memory_context,
    agent_call=None,
):
    if agent_call is None:
        from agent.controller import (
            run_agent,
        )

        agent_call = run_agent

    runtime_memory_context = normalize_runtime_memory_context(memory_context)

    memory_service = StaticMemoryService(runtime_memory_context)

    response = agent_call(
        query,
        memory_service=memory_service,
    )

    if (
        not isinstance(
            response,
            str,
        )
        or not response.strip()
    ):
        raise ValueError("agent response must be a non-empty string")

    return response
