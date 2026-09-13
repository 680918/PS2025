from dataclasses import dataclass


@dataclass
class RAGDiagnosis:
    retrieval_ok: bool
    answer_ok: bool
    failure_stage: str | None


def diagnose_rag_case(
    retrieved_chunk_ids,
    expected_chunk_id,
    answer_passed,
):
    retrieval_ok = expected_chunk_id in retrieved_chunk_ids

    if not retrieval_ok:
        return RAGDiagnosis(
            retrieval_ok=False,
            answer_ok=answer_passed,
            failure_stage="retrieval",
        )

    if not answer_passed:
        return RAGDiagnosis(
            retrieval_ok=True,
            answer_ok=False,
            failure_stage="generation_or_evaluation",
        )

    return RAGDiagnosis(
        retrieval_ok=True,
        answer_ok=True,
        failure_stage=None,
    )


def evaluate_retrieval_rank(
    retrieval_results,
    expected_keyword,
):
    if not expected_keyword:
        return {
            "top1_hit": False,
            "topk_hit": False,
            "expected_rank": None,
        }

    expected_rank = None

    for rank, result in enumerate(
        retrieval_results,
        start=1,
    ):
        if expected_keyword in result.chunk.content:
            expected_rank = rank
            break

    return {
        "top1_hit": expected_rank == 1,
        "topk_hit": expected_rank is not None,
        "expected_rank": expected_rank,
    }
