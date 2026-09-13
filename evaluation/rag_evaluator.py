from dataclasses import dataclass


@dataclass
class RAGEvaluationCase:
    query: str
    expected_keywords: list[str]
    expected_boundary_keywords: list[str] | None = None


@dataclass
class RAGEvaluationResult:
    query: str
    matched_keywords: list[str]
    missing_keywords: list[str]
    passed: bool


def evaluate_answer(answer, case):
    matched_keywords = []
    missing_keywords = []

    all_expected_keywords = list(
        case.expected_keywords
    )

    if case.expected_boundary_keywords:
        all_expected_keywords.extend(
            case.expected_boundary_keywords
        )

    for keyword in all_expected_keywords:
        if keyword in answer:
            matched_keywords.append(keyword)
        else:
            missing_keywords.append(keyword)

    passed = len(missing_keywords) == 0

    return RAGEvaluationResult(
        query=case.query,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        passed=passed,
    )