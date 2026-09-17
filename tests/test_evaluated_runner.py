from agent.state import AgentState
from agent.evaluated_runner import (
    build_evaluated_agent_result,
    run_agent_with_evaluation,
)


def test_evaluated_agent_result_should_include_response_and_evaluation():
    state = AgentState("我下一步应该学习什么？")

    evaluation_result = {
        "goal_alignment": 1.0,
        "actionability": 1.0,
        "memory_usage": 1.0,
        "knowledge_usage": 1.0,
        "response_policy": 1.0,
        "overall_score": 1.0,
        "passed": True,
        "findings": [],
        "improvement_suggestions": [],
    }

    result = build_evaluated_agent_result(
        response="下一步继续练习 Tool Calling。",
        state=state,
        evaluation_result=evaluation_result,
    )

    assert result["response"] == ("下一步继续练习 Tool Calling。")
    assert result["state"] is state
    assert result["evaluation_result"] == evaluation_result


def test_run_agent_with_evaluation_should_return_response_and_evaluation(
    tmp_path,
    monkeypatch,
):
    state = AgentState("我下一步应该学习什么？")

    state.set_memory_context(
        {
            "learning_goal": "一年内学会搭建AI智能体",
        }
    )

    def fake_run_runtime(
        user_message,
        memory_service=None,
        knowledge_service=None,
        document_ids=None,
    ):
        return (
            state,
            "下一步继续练习 Tool Calling。",
        )

    def fake_run_evaluation(
        state,
        response,
        output_dir,
    ):
        return {
            "evaluation_result": {
                "overall_score": 1.0,
                "passed": True,
            },
            "history_path": output_dir / "agent_evaluation_001.json",
            "comparison": None,
            "comparison_path": None,
        }

    monkeypatch.setattr(
        "agent.evaluated_runner.run_agent_runtime",
        fake_run_runtime,
    )

    monkeypatch.setattr(
        "agent.evaluated_runner.run_agent_state_evaluation_pipeline",
        fake_run_evaluation,
    )

    result = run_agent_with_evaluation(
        user_message="我下一步应该学习什么？",
        output_dir=tmp_path,
    )

    assert result["response"] == ("下一步继续练习 Tool Calling。")

    assert result["state"] is state

    assert result["evaluation_result"]["overall_score"] == 1.0
