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


def test_calibration_dataset_items_should_have_relevance_levels():

    cases = get_calibration_cases()

    for case in cases:
        relevance_levels = {item["relevance"] for item in case["items"]}

        assert 0 in relevance_levels
        assert 1 in relevance_levels
        assert 2 in relevance_levels


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
