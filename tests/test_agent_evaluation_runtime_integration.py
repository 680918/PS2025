from agent.state import AgentState
from evaluation.agent_evaluation_adapter import (
    run_agent_state_evaluation_pipeline,
)


def test_agent_runtime_state_should_flow_into_evaluation_pipeline(
    tmp_path,
):
    state = AgentState("我下一步应该学习什么？")

    state.set_memory_context(
        {
            "learning_goal": "一年内学会搭建AI智能体",
        }
    )

    state.set_knowledge_context(
        [
            {
                "content": "Tool Calling 是 Agent 的重要能力。",
                "source": "agent_notes.txt",
            }
        ]
    )

    final_response = (
        "根据你一年内学会搭建AI智能体的目标，"
        "下一步继续练习 Tool Calling。"
        "来源：agent_notes.txt"
    )

    result = run_agent_state_evaluation_pipeline(
        state=state,
        response=final_response,
        output_dir=tmp_path,
    )

    assert result["evaluation_result"]["memory_usage"] == 1.0
    assert result["evaluation_result"]["knowledge_usage"] == 1.0
    assert result["evaluation_result"]["response_policy"] == 1.0

    assert result["history_path"].exists()
