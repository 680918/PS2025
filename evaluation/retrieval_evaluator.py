from dataclasses import dataclass



@dataclass
class RetrievalEvaluationCase:
    query: str
    expected_chunk_id: str

@dataclass
class RetrievalCaseResult:
    query: str
    expected_chunk_id: str
    retrieved_chunk_ids: list[str]
    hit: bool

def hit_at_k(
    results,
    expected_chunk_id,
    k,
):
    if k <= 0:
        raise ValueError("k 必须大于 0")

    top_results = results[:k]

    return any(
        result.chunk.id == expected_chunk_id
        for result in top_results
    )

def evaluate_retrieval(
    retriever,
    cases,
    k=3,
):
    if k <= 0:
        raise ValueError("k 必须大于 0")

    case_results = []
    hits = 0

    for case in cases:
        results = retriever(
            case.query,
            k,
        )

        hit = hit_at_k(
            results,
            case.expected_chunk_id,
            k,
        )

        if hit:
            hits += 1

        case_results.append(
            RetrievalCaseResult(
                query=case.query,
                expected_chunk_id=case.expected_chunk_id,
                retrieved_chunk_ids=[
                    result.chunk.id
                    for result in results[:k]
                ],
                hit=hit,
            )
        )

    total = len(cases)

    return {
        "total": total,
        "hits": hits,
        "hit_rate": (
            hits / total
            if total
            else 0.0
        ),
        "cases": case_results,
    }