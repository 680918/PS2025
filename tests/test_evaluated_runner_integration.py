from agent.evaluated_runner import (
    run_agent_with_evaluation,
)
from agent.state import AgentState


def test_evaluated_runner_should_complete_full_quality_flow(
    tmp_path,
    monkeypatch,
):
    first_state = AgentState("我下一步应该学习什么？")

    first_state.set_memory_context(
        {
            "learning_goal": "一年内学会搭建AI智能体",
        }
    )

    second_state = AgentState("我下一步应该学习什么？")

    second_state.set_memory_context(
        {
            "learning_goal": "一年内学会搭建AI智能体",
        }
    )

    runtime_results = [
        (
            first_state,
            "你可以学习一些人工智能相关知识。",
        ),
        (
            second_state,
            ("根据你一年内学会搭建AI智能体的目标，下一步继续练习 Tool Calling。"),
        ),
    ]

    def fake_run_agent_runtime(
        user_message,
        memory_service=None,
        knowledge_service=None,
        document_ids=None,
    ):
        return runtime_results.pop(0)

    monkeypatch.setattr(
        "agent.evaluated_runner.run_agent_runtime",
        fake_run_agent_runtime,
    )

    first_result = run_agent_with_evaluation(
        user_message="我下一步应该学习什么？",
        output_dir=tmp_path,
    )

    assert first_result["response"] == ("你可以学习一些人工智能相关知识。")

    assert first_result["state"] is first_state

    assert first_result["evaluation_result"]["overall_score"] < 1.0

    assert first_result["history_path"].exists()

    assert first_result["comparison"] is None
    assert first_result["comparison_path"] is None

    second_result = run_agent_with_evaluation(
        user_message="我下一步应该学习什么？",
        output_dir=tmp_path,
    )

    assert second_result["state"] is second_state

    assert (
        second_result["evaluation_result"]["overall_score"]
        > first_result["evaluation_result"]["overall_score"]
    )

    assert second_result["comparison"] is not None

    assert second_result["comparison"]["status"] == "improved"

    assert second_result["comparison_path"] is not None
    assert second_result["comparison_path"].exists()
