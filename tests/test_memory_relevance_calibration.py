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


def test_stock_calibration_should_distinguish_strong_from_partial_relevance():
    items = [
        {
            "memory_key": "learning_feedback:stock-strategy",
            "content": "A股 strategy optimization",
            "relevance": 2,
        },
        {
            "memory_key": "learning_feedback:factor-model",
            "content": "Factor model research",
            "relevance": 1,
        },
        {
            "memory_key": "learning_feedback:english",
            "content": "English vocabulary review",
            "relevance": 0,
        },
    ]

    result = evaluate_calibration_case(
        query="继续优化股票策略系统",
        items=items,
    )

    scores = {item["memory_key"]: item["score"] for item in result["scored_items"]}

    assert (
        scores["learning_feedback:stock-strategy"]
        > scores["learning_feedback:factor-model"]
        > scores["learning_feedback:english"]
    )


def test_tool_calling_calibration_should_recognize_agent_tool_integration_as_partial():
    items = [
        {
            "memory_key": "learning_feedback:tool-calling",
            "content": "Tool Calling design and practice",
            "relevance": 2,
        },
        {
            "memory_key": "learning_feedback:agent-tools",
            "content": "AI Agent tool integration",
            "relevance": 1,
        },
        {
            "memory_key": "learning_feedback:english-tool",
            "content": "English vocabulary lesson about the word tool",
            "relevance": 0,
        },
    ]

    result = evaluate_calibration_case(
        query="继续学习工具调用",
        items=items,
    )

    scores = {item["memory_key"]: item["score"] for item in result["scored_items"]}

    assert (
        scores["learning_feedback:tool-calling"]
        > scores["learning_feedback:agent-tools"]
        > scores["learning_feedback:english-tool"]
    )


def test_calibration_case_should_report_pairwise_violations():
    items = [
        {
            "memory_key": "learning_feedback:strong",
            "content": "Tool Calling practice",
            "relevance": 2,
        },
        {
            "memory_key": "learning_feedback:partial",
            "content": "Unrelated content",
            "relevance": 1,
        },
        {
            "memory_key": "learning_feedback:irrelevant",
            "content": "Another unrelated memory",
            "relevance": 0,
        },
    ]

    result = evaluate_calibration_case(
        query="Tool Calling",
        items=items,
    )

    assert "pairwise_violations" in result
    assert len(result["pairwise_violations"]) >= 1

    violations = result["pairwise_violations"]

    assert len(violations) == 1

    violation = violations[0]

    assert violation["higher_relevance_key"] == "learning_feedback:partial"
    assert violation["higher_relevance"] == 1
    assert violation["higher_score"] == 0.0

    assert violation["lower_relevance_key"] == "learning_feedback:irrelevant"
    assert violation["lower_relevance"] == 0
    assert violation["lower_score"] == 0.0


def test_calibration_case_should_report_minimum_pairwise_margin():
    items = [
        {
            "memory_key": "learning_feedback:strong",
            "content": "Python Tool Calling practice",
            "relevance": 2,
        },
        {
            "memory_key": "learning_feedback:partial",
            "content": "Python basics",
            "relevance": 1,
        },
        {
            "memory_key": "learning_feedback:irrelevant",
            "content": "English vocabulary review",
            "relevance": 0,
        },
    ]

    result = evaluate_calibration_case(
        query="继续学习 Python Tool Calling",
        items=items,
    )

    assert "minimum_pairwise_margin" in result
    assert result["minimum_pairwise_margin"] == 0.5


def test_calibration_dataset_should_report_margin_summary():
    cases = [
        {
            "name": "case_one",
            "query": "Python Tool Calling",
            "items": [
                {
                    "memory_key": "strong",
                    "content": "Python Tool Calling",
                    "relevance": 2,
                },
                {
                    "memory_key": "partial",
                    "content": "Python basics",
                    "relevance": 1,
                },
                {
                    "memory_key": "irrelevant",
                    "content": "English vocabulary",
                    "relevance": 0,
                },
            ],
        }
    ]

    result = evaluate_calibration_dataset(cases)

    assert "minimum_pairwise_margin" in result
    assert "average_minimum_pairwise_margin" in result

    assert result["minimum_pairwise_margin"] == 0.5
    assert result["average_minimum_pairwise_margin"] == 0.5
