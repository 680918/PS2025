from evaluation.agent_evaluation_batch import (
    evaluate_agent_cases,
)
from evaluation.agent_evaluation_cases import (
    AGENT_EVALUATION_CASES,
)


def test_evaluate_agent_cases_should_return_case_results():
    cases = [
        {
            "case_id": "case_001",
            "focus_metric": "goal_alignment",
            "user_message": "我想学习 Tool Calling。",
            "response": "下一步继续学习 Tool Calling。",
            "memory_context": {},
            "knowledge_context": [],
        },
        {
            "case_id": "case_002",
            "focus_metric": "actionability",
            "user_message": "我应该怎么练习？",
            "response": "第一步运行测试，然后记录结果。",
            "memory_context": {},
            "knowledge_context": [],
        },
    ]

    result = evaluate_agent_cases(cases)

    assert len(result["cases"]) == 2

    assert result["cases"][0]["case_id"] == "case_001"
    assert result["cases"][1]["case_id"] == "case_002"

    assert "evaluation_result" in result["cases"][0]
    assert "evaluation_result" in result["cases"][1]


def test_evaluate_agent_cases_should_return_average_metrics():
    cases = [
        {
            "case_id": "case_001",
            "focus_metric": "goal_alignment",
            "user_message": "我想学习 Tool Calling。",
            "response": "下一步继续学习 Tool Calling。",
            "memory_context": {},
            "knowledge_context": [],
        },
        {
            "case_id": "case_002",
            "focus_metric": "actionability",
            "user_message": "我应该怎么练习？",
            "response": "第一步运行测试，然后记录结果。",
            "memory_context": {},
            "knowledge_context": [],
        },
    ]

    result = evaluate_agent_cases(cases)

    assert "average_metrics" in result

    expected_keys = {
        "goal_alignment",
        "actionability",
        "memory_usage",
        "knowledge_usage",
        "response_policy",
        "overall_score",
    }

    assert set(result["average_metrics"].keys()) == expected_keys

    for value in result["average_metrics"].values():
        assert 0.0 <= value <= 1.0


def test_agent_evaluation_benchmark_should_evaluate_all_cases():
    result = evaluate_agent_cases(AGENT_EVALUATION_CASES)

    assert len(result["cases"]) == len(AGENT_EVALUATION_CASES)

    assert len(result["cases"]) == 5

    assert 0.0 <= result["average_metrics"]["overall_score"] <= 1.0
