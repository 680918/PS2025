from evaluation.agent_evaluation_cases import (
    AGENT_EVALUATION_CASES,
)


def test_agent_evaluation_cases_should_have_stable_contract():
    assert len(AGENT_EVALUATION_CASES) > 0

    required_keys = {
        "case_id",
        "focus_metric",
        "user_message",
        "response",
        "memory_context",
        "knowledge_context",
    }

    for case in AGENT_EVALUATION_CASES:
        assert required_keys.issubset(case.keys())


def test_agent_evaluation_case_ids_should_be_unique():
    case_ids = [case["case_id"] for case in AGENT_EVALUATION_CASES]

    assert len(case_ids) == len(set(case_ids))


def test_agent_evaluation_cases_should_cover_core_metrics():
    expected_metrics = {
        "goal_alignment",
        "actionability",
        "memory_usage",
        "knowledge_usage",
        "response_policy",
    }

    actual_metrics = {case["focus_metric"] for case in AGENT_EVALUATION_CASES}

    assert actual_metrics == expected_metrics
