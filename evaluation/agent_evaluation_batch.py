from evaluation.agent_evaluation import (
    evaluate_agent_response,
)


METRIC_NAMES = (
    "goal_alignment",
    "actionability",
    "memory_usage",
    "knowledge_usage",
    "response_policy",
    "overall_score",
)


def evaluate_agent_cases(cases):
    case_results = []

    for case in cases:
        evaluation_result = evaluate_agent_response(
            user_message=case["user_message"],
            response=case["response"],
            memory_context=case["memory_context"],
            knowledge_context=case["knowledge_context"],
        )

        case_results.append(
            {
                "case_id": case["case_id"],
                "focus_metric": case["focus_metric"],
                "evaluation_result": evaluation_result,
            }
        )

    average_metrics = calculate_average_metrics(case_results)

    return {
        "cases": case_results,
        "average_metrics": average_metrics,
    }


def calculate_average_metrics(case_results):
    if not case_results:
        return {metric_name: 0.0 for metric_name in METRIC_NAMES}

    return {
        metric_name: sum(
            case["evaluation_result"][metric_name] for case in case_results
        )
        / len(case_results)
        for metric_name in METRIC_NAMES
    }
