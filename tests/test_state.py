import pytest

from agent.state import AgentState
from memory.service import MemoryService
from memory.store import MemoryStore
from coach.context_models import CoachContext
from agent.context_intelligence_trace import (
    ContextIntelligenceTrace,
)
from agent.context_intelligence_result import (
    ContextIntelligenceResult,
)
from agent.evaluation_report import (
    EvaluationReport,
)
from agent.evaluation_models import (
    EvaluationResult,
)


pytestmark = pytest.mark.unit


def test_retry_limit():

    state = AgentState("测试")  # 创建State

    assert state.can_retry() is True  # 检查：一开始能不能Retry？-是的

    state.record_retry()  # 记录一次Retry

    assert state.can_retry() is False  # 再检查：还能不能Retry？-应该是False


def test_replan_limit():

    state = AgentState("测试")

    assert state.can_replan() is True

    state.record_replan()

    assert state.can_replan() is False


def test_agent_state_has_run_id():

    state = AgentState("hello")

    assert state.run_id
    assert isinstance(state.run_id, str)


def test_agent_state_run_id_is_unique():

    state1 = AgentState("hello")
    state2 = AgentState("hello")

    assert state1.run_id != state2.run_id


def test_get_state_includes_run_id():

    state = AgentState("hello")

    data = state.get_state()

    assert "run_id" in data
    assert data["run_id"] == state.run_id


def test_get_state_includes_status():

    state = AgentState("hello")
    state.status = "success"

    result = state.get_state()

    assert result["status"] == "success"


def test_get_state_includes_last_result():

    state = AgentState("hello")

    state.last_result = {
        "status": "error",
        "error_type": "tool_error",
        "message": "tool failed",
    }

    result = state.get_state()

    assert result["last_result"]["status"] == "error"
    assert result["last_result"]["error_type"] == "tool_error"


def test_get_state_includes_failure_stage():

    state = AgentState("hello")
    state.failure_stage = "tool"

    result = state.get_state()

    assert result["failure_stage"] == "tool"


def test_agent_state_stores_memory_context():

    state = AgentState("我今天应该学习什么？")

    memory_context = {
        "skill": [
            {
                "memory_key": "python_skill",
                "content": "用户正在学习 Python",
            }
        ]
    }

    state.set_memory_context(memory_context)

    assert state.memory_context == memory_context
    assert state.get_state()["memory_context"] == memory_context


def test_agent_state_stores_memory_service_dependency():

    store = MemoryStore()
    memory_service = MemoryService(store)

    state = AgentState(
        "测试问题",
        memory_service=memory_service,
    )

    assert state.memory_service is memory_service


def test_memory_service_dependency_is_not_exposed_in_state_data():

    store = MemoryStore()
    memory_service = MemoryService(store)

    state = AgentState(
        "测试问题",
        memory_service=memory_service,
    )

    state_data = state.get_state()

    assert "memory_service" not in state_data


def test_agent_state_should_store_routing_trace():
    state = AgentState("test")

    routing_trace = {
        "selected_document_ids": ["doc-agent"],
        "candidates": [
            {
                "document_id": "doc-agent",
                "score": 4,
                "selected": True,
                "reason": "selected",
            }
        ],
    }

    state.set_routing_trace(routing_trace)

    assert state.routing_trace == routing_trace
    assert state.get_state()["routing_trace"] == routing_trace


def test_agent_state_should_default_routing_trace_to_none():
    state = AgentState("test")

    assert state.routing_trace is None
    assert state.get_state()["routing_trace"] is None


def test_agent_state_should_store_memory_reliability_trace():
    state = AgentState("test")

    trace = {
        "candidates": {
            "total": 3,
        },
        "injected": {
            "total": 2,
        },
    }

    state.set_memory_reliability_trace(trace)

    assert state.memory_reliability_trace == trace

    assert state.get_state()["memory_reliability_trace"] == trace


def test_agent_state_should_default_memory_reliability_trace_to_none():
    state = AgentState("test")

    assert state.memory_reliability_trace is None

    assert state.get_state()["memory_reliability_trace"] is None


def test_agent_state_should_start_without_coach_context():
    state = AgentState("hello")

    assert state.coach_context is None


def test_agent_state_should_store_coach_context():
    state = AgentState("hello")

    coach_context = CoachContext(
        user_context={"name": "Test User"},
        learning_context={"domain": "AI Agent"},
        memory_context={"learning": []},
    )

    state.set_coach_context(coach_context)

    assert state.coach_context is coach_context


def test_agent_state_should_store_conversation_context():
    state = AgentState("那第二种呢？")

    conversation_context = [
        {
            "role": "user",
            "content": "Memory 有哪两种读取模式？",
        },
        {
            "role": "assistant",
            "content": "第一种是隐式注入，第二种是显式工具调用。",
        },
    ]

    state.set_conversation_context(
        conversation_context,
    )

    assert state.conversation_context == conversation_context


def test_agent_state_should_start_with_empty_conversation_context():
    state = AgentState("hello")

    assert state.conversation_context == []


def test_agent_state_should_store_assembled_context():
    state = AgentState(
        "继续学习",
    )

    assembled_context = object()

    state.set_assembled_context(
        assembled_context,
    )

    assert state.assembled_context is assembled_context


def test_agent_state_should_store_projected_contexts():

    state = AgentState(
        "continue learning",
    )

    projected_contexts = {
        "learning_continuity": {
            "learning.current_topic": "AI Agent",
        },
        "memory": {
            "learning.completed_understanding": 80,
        },
    }

    state.set_projected_contexts(
        projected_contexts,
    )

    assert state.projected_contexts == projected_contexts


def test_agent_state_should_store_context_conflicts():

    state = AgentState(
        "test",
    )

    conflicts = {
        "learning.current_topic": [
            "Memory",
            "Tool Calling",
        ]
    }

    state.set_context_conflicts(
        conflicts,
    )

    assert state.context_conflicts == conflicts


def test_agent_state_should_store_context_resolutions():

    state = AgentState(
        "test",
    )

    resolutions = {
        "learning.current_topic": {
            "source": "conversation",
            "value": "Memory",
        }
    }

    state.set_context_resolutions(
        resolutions,
    )

    assert state.context_resolutions == resolutions


def test_agent_state_should_store_context_resolution_trace():

    state = AgentState(
        "test",
    )

    trace = {
        "learning.current_topic": {
            "winner": "conversation",
            "reason": "higher priority",
        }
    }

    state.set_context_resolution_trace(
        trace,
    )

    assert state.context_resolution_trace == trace


def test_agent_state_should_store_context_evaluation_results():

    state = AgentState(
        "test",
    )

    results = {
        "policy_compliance": {
            "passed": True,
        }
    }

    state.set_context_evaluation_results(
        results,
    )

    assert state.context_evaluation_results == results


def test_agent_state_should_store_context_evaluation_result_objects():

    state = AgentState(
        "test",
    )

    results = {
        "policy_compliance": {
            "learning.current_topic": EvaluationResult(
                metric="policy_compliance",
                passed=True,
                details={
                    "expected": "conversation",
                    "actual": "conversation",
                },
            )
        }
    }

    state.set_context_evaluation_results(
        results,
    )

    assert (
        state.context_evaluation_results["policy_compliance"][
            "learning.current_topic"
        ].passed
        is True
    )


def test_agent_state_should_store_context_evaluation_report():

    state = AgentState(
        "test",
    )

    report = EvaluationReport(
        passed=True,
        evaluations={},
        summary={
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 0,
        },
    )

    state.set_context_evaluation_report(
        report,
    )

    assert state.context_evaluation_report is report


def test_agent_state_should_store_context_intelligence_trace():

    state = AgentState(
        "test",
    )

    trace = ContextIntelligenceTrace(
        assembled_context="context",
        conflicts={},
        resolutions={},
        evaluations={},
        report="report",
    )

    state.set_context_intelligence_trace(
        trace,
    )

    assert state.context_intelligence_trace is trace

    assert state.get_state()["context_intelligence_trace"] is trace


def test_agent_state_should_store_context_intelligence_result():

    state = AgentState(
        "test",
    )

    result = ContextIntelligenceResult(
        context="context",
        conflicts={},
        resolutions={},
        report="report",
    )

    state.set_context_intelligence_result(
        result,
    )

    assert state.context_intelligence_result is result

    assert state.get_state()["context_intelligence_result"] is result


def test_agent_state_should_store_pending_knowledge_candidate():

    state = AgentState(
        "test",
    )

    candidate = {"topic": "Memory"}

    state.set_pending_knowledge_candidate(
        candidate,
    )

    assert state.pending_knowledge_candidate == candidate

    assert state.get_state()["pending_knowledge_candidate"] == candidate
