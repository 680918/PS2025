from memory.memory_conflict_evaluator import (
    evaluate_memory_conflict_case,
)


def _summarize_results(
    results,
):
    total_cases = len(results)

    if total_cases == 0:
        return {
            "total_cases": 0,
            "correct_cases": 0,
            "error_cases": 0,
            "accuracy": 0.0,
        }

    correct_cases = sum(1 for result in results if result["is_correct"])

    return {
        "total_cases": total_cases,
        "correct_cases": (correct_cases),
        "error_cases": (total_cases - correct_cases),
        "accuracy": (correct_cases / total_cases),
    }


def run_memory_conflict_evaluation(
    cases,
):
    results = [evaluate_memory_conflict_case(case) for case in cases]

    errors = [result for result in results if not result["is_correct"]]

    return {
        "results": results,
        "errors": errors,
        "summary": (_summarize_results(results)),
    }
