from agent.state import AgentState
from evaluation.agent_evaluation_adapter import (
    build_agent_evaluation_input,
    evaluate_agent_state_response,
    run_agent_state_evaluation_pipeline,
)


def test_agent_evaluation_adapter_should_build_input_from_state():
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

    result = build_agent_evaluation_input(
        state=state,
        response="下一步继续练习 Tool Calling。",
    )

    assert result == {
        "user_message": "我下一步应该学习什么？",
        "response": "下一步继续练习 Tool Calling。",
        "memory_context": {
            "learning_goal": "一年内学会搭建AI智能体",
        },
        "knowledge_context": [
            {
                "content": "Tool Calling 是 Agent 的重要能力。",
                "source": "agent_notes.txt",
            }
        ],
    }


def test_agent_evaluation_adapter_should_evaluate_state_response():
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

    result = evaluate_agent_state_response(
        state=state,
        response=(
            "根据你一年内学会搭建AI智能体的目标，"
            "下一步继续练习 Tool Calling。"
            "来源：agent_notes.txt"
        ),
    )

    assert "goal_alignment" in result
    assert "actionability" in result
    assert "memory_usage" in result
    assert "knowledge_usage" in result
    assert "response_policy" in result
    assert "overall_score" in result


def test_agent_evaluation_adapter_should_run_pipeline_from_state(
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

    result = run_agent_state_evaluation_pipeline(
        state=state,
        response=(
            "根据你一年内学会搭建AI智能体的目标，"
            "下一步继续练习 Tool Calling。"
            "来源：agent_notes.txt"
        ),
        output_dir=tmp_path,
    )

    assert "evaluation_result" in result
    assert "history_path" in result
    assert "comparison" in result
    assert "comparison_path" in result
