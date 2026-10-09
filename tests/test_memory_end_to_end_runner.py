from memory.memory_end_to_end_runner import (
    run_memory_end_to_end_evaluation,
)


def test_end_to_end_runner_should_evaluate_cases():
    cases = [
        {
            "case_id": "helpful-case",
            "category": "helpful",
            "domain": "ai_agent",
            "description": "Helpful memory.",
            "query": "Continue learning Tool Calling",
            "memory_context": [
                {
                    "memory_key": "learning:tool-calling",
                    "content": "Needs practical exercises.",
                },
            ],
            "expected_effect": "positive",
            "evaluation_criteria": [
                "Move toward practical execution.",
            ],
        },
    ]

    def fake_agent_call(
        user_message,
        memory_service=None,
        **kwargs,
    ):
        context = memory_service.get_context()

        if context["learning"]:
            return "Let's do a practical exercise."

        return "Tool Calling invokes tools."

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "success",
            "content": ('{"effect": "positive", "reason": "有 Memory 后进入了实践。"}'),
        }

    report = run_memory_end_to_end_evaluation(
        cases,
        agent_call=fake_agent_call,
        llm_call=fake_llm_call,
    )

    assert report["summary"] == {
        "total_cases": 1,
        "correct_cases": 1,
        "error_cases": 0,
        "accuracy": 1.0,
    }

    result = report["results"][0]

    assert result["case_id"] == "helpful-case"
    assert result["category"] == "helpful"
    assert result["expected_effect"] == "positive"
    assert result["actual_effect"] == "positive"
    assert result["is_correct"] is True


def test_end_to_end_runner_should_report_errors():
    cases = [
        {
            "case_id": "neutral-case",
            "category": "neutral",
            "domain": "python",
            "description": "Neutral memory.",
            "query": "Explain Python dictionaries",
            "memory_context": [
                {
                    "memory_key": "profile:study-time",
                    "content": "Prefers afternoon study.",
                },
            ],
            "expected_effect": "neutral",
            "evaluation_criteria": [
                "Explain dictionaries accurately.",
            ],
        },
    ]

    def fake_agent_call(
        user_message,
        memory_service=None,
        **kwargs,
    ):
        return "A dictionary stores key-value pairs."

    def fake_llm_call(
        system_prompt,
        user_message,
    ):
        return {
            "status": "success",
            "content": ('{"effect": "positive", "reason": "测试误判。"}'),
        }

    report = run_memory_end_to_end_evaluation(
        cases,
        agent_call=fake_agent_call,
        llm_call=fake_llm_call,
    )

    assert report["summary"]["accuracy"] == 0.0
    assert len(report["errors"]) == 1
    assert report["errors"][0]["case_id"] == "neutral-case"


def test_end_to_end_runner_should_handle_empty_cases():
    report = run_memory_end_to_end_evaluation(
        [],
        agent_call=None,
        llm_call=None,
    )

    assert report == {
        "results": [],
        "errors": [],
        "summary": {
            "total_cases": 0,
            "correct_cases": 0,
            "error_cases": 0,
            "accuracy": 0.0,
        },
    }
