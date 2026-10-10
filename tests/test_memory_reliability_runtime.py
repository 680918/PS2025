import agent.controller as controller


class StubMemoryService:
    def __init__(
        self,
        memory_context,
    ):
        self.memory_context = memory_context

    def get_context(self):
        return self.memory_context


def _empty_context():
    return {
        "profile": [],
        "skill": [],
        "learning": [],
        "project": [],
        "experience": [],
    }


def test_run_agent_runtime_should_store_memory_reliability_trace(
    monkeypatch,
):
    raw_context = _empty_context()

    raw_context["learning"] = [
        {
            "memory_key": "trusted-python",
            "content": ("Needs Python practice."),
            "confidence": 0.8,
        },
        {
            "memory_key": "blocked-python",
            "content": ("Fully mastered Python."),
            "confidence": 0.0,
        },
        {
            "memory_key": "extra-python",
            "content": ("Extra Python memory."),
            "confidence": 0.8,
        },
    ]

    blocked_by_trust = _empty_context()

    blocked_by_trust["learning"] = [raw_context["learning"][1]]

    before_budget = _empty_context()

    before_budget["learning"] = [
        raw_context["learning"][0],
        raw_context["learning"][2],
    ]

    after_budget = _empty_context()

    after_budget["learning"] = [
        raw_context["learning"][0],
    ]

    diagnostics = {
        "blocked_by_trust": (blocked_by_trust),
        "before_budget": (before_budget),
        "after_budget": (after_budget),
    }

    monkeypatch.setattr(
        controller,
        ("select_relevant_memory_context_with_budget_diagnostics"),
        lambda *args, **kwargs: diagnostics,
    )

    monkeypatch.setattr(
        controller,
        "route_task",
        lambda user_message: "simple",
    )

    monkeypatch.setattr(
        controller,
        "run_simple_agent",
        lambda user_message, state: "ok",
    )

    state, response = controller.run_agent_runtime(
        "How should I study Python?",
        memory_service=(StubMemoryService(raw_context)),
    )

    trace = state.memory_reliability_trace

    assert response == "ok"

    assert trace["candidates"]["total"] == 3

    assert trace["blocked_by_trust"]["total"] == 1

    assert trace["selected_before_budget"]["total"] == 2

    assert trace["removed_by_budget"]["total"] == 1

    assert trace["injected"]["total"] == 1

    assert trace["injected"]["memory_keys_by_type"]["learning"] == [
        "trusted-python",
    ]

    assert state.get_state()["memory_reliability_trace"] == trace

    assert trace["trusted_candidates"]["total"] == 2

    assert trace["not_selected_before_budget"]["total"] == 0


def test_run_agent_runtime_should_persist_memory_reliability_run_record(
    monkeypatch,
):
    raw_context = _empty_context()

    raw_context["learning"] = [
        {
            "memory_key": "python-practice",
            "content": "Needs Python practice.",
            "confidence": 0.8,
        },
    ]

    diagnostics = {
        "blocked_by_trust": (_empty_context()),
        "before_budget": (raw_context),
        "after_budget": (raw_context),
    }

    saved_records = []

    class FakeRunRecordStore:
        def save(
            self,
            record,
        ):
            saved_records.append(record)

    monkeypatch.setattr(
        controller,
        ("select_relevant_memory_context_with_budget_diagnostics"),
        lambda *args, **kwargs: diagnostics,
    )

    monkeypatch.setattr(
        controller,
        "route_task",
        lambda user_message: "simple",
    )

    monkeypatch.setattr(
        controller,
        "run_simple_agent",
        lambda user_message, state: "ok",
    )

    state, response = controller.run_agent_runtime(
        "How should I study Python?",
        memory_service=(StubMemoryService(raw_context)),
        memory_reliability_run_record_store=(FakeRunRecordStore()),
    )

    assert response == "ok"

    assert len(saved_records) == 1

    record = saved_records[0]

    assert record["run_id"] == state.run_id

    assert record["schema_version"] == 1

    assert record["candidates"] == 1

    assert record["blocked_by_trust"] == 0

    assert record["trusted_candidates"] == 1

    assert record["not_selected_before_budget"] == 0

    assert record["selected_before_budget"] == 1

    assert record["removed_by_budget"] == 0

    assert record["injected"] == 1

    assert (
        isinstance(
            record["created_at"],
            str,
        )
        and record["created_at"]
    )


def test_run_agent_runtime_should_not_require_run_record_store(
    monkeypatch,
):
    raw_context = _empty_context()

    diagnostics = {
        "blocked_by_trust": (_empty_context()),
        "before_budget": (_empty_context()),
        "after_budget": (_empty_context()),
    }

    monkeypatch.setattr(
        controller,
        ("select_relevant_memory_context_with_budget_diagnostics"),
        lambda *args, **kwargs: diagnostics,
    )

    monkeypatch.setattr(
        controller,
        "route_task",
        lambda user_message: "simple",
    )

    monkeypatch.setattr(
        controller,
        "run_simple_agent",
        lambda user_message, state: "ok",
    )

    state, response = controller.run_agent_runtime(
        "hello",
        memory_service=(StubMemoryService(raw_context)),
    )

    assert response == "ok"

    assert state.memory_reliability_trace is not None
