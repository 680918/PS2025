from evaluation.agent_evaluation_pipeline import (
    run_agent_evaluation_pipeline,
)


def test_agent_evaluation_pipeline_should_return_core_results(
    tmp_path,
):
    result = run_agent_evaluation_pipeline(
        user_message="我下一步应该学什么？",
        response=("根据你一年内学会搭建AI智能体的目标，下一步继续加强Python实践。"),
        memory_context={
            "learning_goal": "一年内学会搭建AI智能体",
        },
        knowledge_context=None,
        output_dir=tmp_path,
    )

    assert "evaluation_result" in result
    assert "history_path" in result
    assert "comparison" in result
    assert "comparison_path" in result


def test_agent_evaluation_pipeline_should_compare_with_previous_run(
    tmp_path,
):
    first_result = run_agent_evaluation_pipeline(
        user_message="我下一步应该学什么？",
        response="你可以学习一些人工智能相关知识。",
        memory_context={
            "learning_goal": "一年内学会搭建AI智能体",
        },
        knowledge_context=None,
        output_dir=tmp_path,
    )

    assert first_result["comparison"] is None
    assert first_result["comparison_path"] is None

    second_result = run_agent_evaluation_pipeline(
        user_message="我下一步应该学什么？",
        response=("根据你一年内学会搭建AI智能体的目标，下一步继续加强Python实践。"),
        memory_context={
            "learning_goal": "一年内学会搭建AI智能体",
        },
        knowledge_context=None,
        output_dir=tmp_path,
    )

    assert second_result["comparison"] is not None
    assert second_result["comparison"]["status"] == "improved"

    assert second_result["comparison_path"] is not None
    assert second_result["comparison_path"].exists()
