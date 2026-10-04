from memory.relevance_calibration import (
    calculate_pairwise_order_accuracy,
    evaluate_calibration_case,
    evaluate_calibration_dataset,
)


def test_pairwise_order_accuracy_should_be_perfect_when_scores_are_correctly_ordered():
    scored_items = [
        {
            "score": 1.0,
            "relevance": 2,
        },
        {
            "score": 0.5,
            "relevance": 1,
        },
        {
            "score": 0.0,
            "relevance": 0,
        },
    ]

    accuracy = calculate_pairwise_order_accuracy(
        scored_items,
    )

    assert accuracy == 1.0


def test_pairwise_order_accuracy_should_drop_when_scores_are_misordered():
    scored_items = [
        {
            "score": 1.0,
            "relevance": 2,
        },
        {
            "score": 0.2,
            "relevance": 1,
        },
        {
            "score": 0.5,
            "relevance": 0,
        },
    ]

    accuracy = calculate_pairwise_order_accuracy(
        scored_items,
    )

    assert accuracy < 1.0
    assert accuracy > 0.0


def test_evaluate_calibration_case_should_use_real_memory_scores():
    items = [
        {
            "memory_key": "learning_feedback:python-tool-calling",
            "content": "Python Tool Calling practice",
            "relevance": 2,
        },
        {
            "memory_key": "learning_feedback:python-basics",
            "content": "Python basics",
            "relevance": 1,
        },
        {
            "memory_key": "learning_feedback:english",
            "content": "English vocabulary review",
            "relevance": 0,
        },
    ]

    result = evaluate_calibration_case(
        query="继续学习 Python Tool Calling",
        items=items,
    )

    assert result["pairwise_order_accuracy"] == 1.0

    scored_items = result["scored_items"]

    assert (
        scored_items[0]["score"] > scored_items[1]["score"] > scored_items[2]["score"]
    )


def test_evaluate_calibration_dataset_should_average_case_accuracy():
    cases = [
        {
            "name": "python_tool_calling",
            "query": "继续学习 Python Tool Calling",
            "items": [
                {
                    "memory_key": "learning_feedback:python-tool-calling",
                    "content": "Python Tool Calling practice",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:python-basics",
                    "content": "Python basics",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:english",
                    "content": "English vocabulary review",
                    "relevance": 0,
                },
            ],
        },
        {
            "name": "reading_system",
            "query": "继续培养阅读习惯",
            "items": [
                {
                    "memory_key": "learning_feedback:reading-system",
                    "content": "Build long term reading habit",
                    "relevance": 2,
                },
                {
                    "memory_key": "learning_feedback:book-notes",
                    "content": "Book notes and reflection",
                    "relevance": 1,
                },
                {
                    "memory_key": "learning_feedback:stock",
                    "content": "Stock analysis",
                    "relevance": 0,
                },
            ],
        },
    ]

    result = evaluate_calibration_dataset(
        cases,
    )

    assert len(result["cases"]) == 2
    assert result["average_pairwise_order_accuracy"] == 1.0
    case_results = {case["name"]: case for case in result["cases"]}

    assert case_results["python_tool_calling"]["pairwise_order_accuracy"] == 1.0

    assert case_results["reading_system"]["pairwise_order_accuracy"] == 1.0


def test_reading_calibration_should_distinguish_strong_from_partial_relevance():
    items = [
        {
            "memory_key": "learning_feedback:reading-system",
            "content": "Build long term reading habit",
            "relevance": 2,
        },
        {
            "memory_key": "learning_feedback:book-notes",
            "content": "Book notes and reflection",
            "relevance": 1,
        },
        {
            "memory_key": "learning_feedback:stock",
            "content": "Stock analysis",
            "relevance": 0,
        },
    ]

    result = evaluate_calibration_case(
        query="继续培养阅读习惯",
        items=items,
    )

    scores = {item["memory_key"]: item["score"] for item in result["scored_items"]}

    assert (
        scores["learning_feedback:reading-system"]
        > scores["learning_feedback:book-notes"]
        > scores["learning_feedback:stock"]
    )
