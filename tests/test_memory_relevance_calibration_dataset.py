from memory.relevance_calibration_dataset import (
    get_calibration_cases,
)


def test_calibration_dataset_should_include_multiple_domains():
    cases = get_calibration_cases()

    case_names = {case["name"] for case in cases}

    assert "python_tool_calling" in case_names
    assert "agent_memory" in case_names
    assert "stock_strategy" in case_names
    assert "reading_system" in case_names


def test_calibration_dataset_should_include_relevant_and_irrelevant_items():
    cases = get_calibration_cases()

    for case in cases:
        relevance_levels = {item["relevance"] for item in case["items"]}

        assert 0 in relevance_levels
        assert relevance_levels & {1, 2}


def test_calibration_dataset_should_have_valid_schema():

    cases = get_calibration_cases()

    for case in cases:
        assert "name" in case
        assert "query" in case
        assert "items" in case

        assert isinstance(
            case["items"],
            list,
        )

        for item in case["items"]:
            assert "memory_key" in item
            assert "content" in item
            assert "relevance" in item

            assert item["relevance"] in {
                0,
                1,
                2,
            }


def test_calibration_dataset_should_include_keyword_distractor_case():
    cases = get_calibration_cases()

    case_names = {case["name"] for case in cases}

    assert "tool_calling_keyword_distractor" in case_names


def test_calibration_dataset_should_include_tool_calling_semantic_hard_case():
    cases = get_calibration_cases()

    case_names = {case["name"] for case in cases}

    assert "tool_calling_semantic_hard" in case_names


def test_calibration_dataset_should_include_memory_overload_case():
    cases = get_calibration_cases()

    case_names = {case["name"] for case in cases}

    assert "memory_overload" in case_names


def test_memory_overload_should_treat_both_query_topics_as_strong():
    cases = get_calibration_cases()

    case = next(case for case in cases if case["name"] == "memory_overload")

    relevance_by_key = {item["memory_key"]: item["relevance"] for item in case["items"]}

    assert relevance_by_key["learning_feedback:agent-memory"] == 2
    assert relevance_by_key["learning_feedback:tool-calling"] == 2


def test_calibration_dataset_should_include_agent_memory_semantic_distractor():
    cases = get_calibration_cases()

    case_names = {case["name"] for case in cases}

    assert "agent_memory_semantic_distractor" in case_names
