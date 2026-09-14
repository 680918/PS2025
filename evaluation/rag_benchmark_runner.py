from pathlib import Path

from agent.controller import run_agent
from evaluation.rag_benchmark import (
    build_python_rag_benchmark,
)
from evaluation.rag_diagnosis import (
    evaluate_retrieval_rank,
)
from evaluation.rag_evaluator import (
    RAGEvaluationCase,
    evaluate_answer,
)
from knowledge.evidence_policy import decide_evidence
from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)
from knowledge.service import KnowledgeService


def build_knowledge_service():
    embedding_provider = LocalEmbeddingProvider()

    knowledge_service = KnowledgeService(
        embedding_provider=embedding_provider,
    )

    knowledge_file = Path("data/knowledge/python_basics.txt")

    knowledge_service.add_document(
        knowledge_file,
        chunk_size=25,
        overlap=0,
    )

    return (
        knowledge_service,
        embedding_provider,
    )


def run_benchmark():
    (
        knowledge_service,
        embedding_provider,
    ) = build_knowledge_service()

    benchmark = build_python_rag_benchmark()

    total = len(benchmark)

    answer_passed = 0

    in_scope_total = 0
    in_scope_top1_hits = 0
    in_scope_topk_hits = 0
    in_scope_expected_ranks = []
    in_scope_top1_scores = []

    out_of_scope_total = 0
    out_of_scope_expected_misses = 0
    out_of_scope_top1_scores = []

    evidence_total = 0
    evidence_correct = 0
    evidence_false_positive = 0
    evidence_false_negative = 0

    for index, item in enumerate(
        benchmark,
        start=1,
    ):
        retrieval_results = knowledge_service.search(
            item.query,
            top_k=3,
        )

        answer = run_agent(
            item.query,
            knowledge_service=knowledge_service,
        )

        evaluation_case = RAGEvaluationCase(
            query=item.query,
            expected_keywords=item.expected_keywords,
            expected_boundary_keywords=(item.expected_boundary_keywords),
        )

        answer_result = evaluate_answer(
            answer,
            evaluation_case,
        )

        if answer_result.passed:
            answer_passed += 1

        rank_result = evaluate_retrieval_rank(
            retrieval_results,
            item.expected_retrieval_keyword,
        )

        top1_score = None

        if retrieval_results:
            top1_score = retrieval_results[0].score

        if item.knowledge_expected:
            in_scope_total += 1

            if rank_result["top1_hit"]:
                in_scope_top1_hits += 1

            if rank_result["topk_hit"]:
                in_scope_topk_hits += 1

            if rank_result["expected_rank"] is not None:
                in_scope_expected_ranks.append(rank_result["expected_rank"])

            if top1_score is not None:
                in_scope_top1_scores.append(top1_score)

        else:
            out_of_scope_total += 1

            if not item.expected_retrieval_keyword:
                out_of_scope_expected_misses += 1

            if top1_score is not None:
                out_of_scope_top1_scores.append(top1_score)

        evidence_decision = decide_evidence(
            query=item.query,
            retrieval_results=retrieval_results,
            embedding_provider=embedding_provider,
        )

        evidence_total += 1

        if evidence_decision.supported == item.knowledge_expected:
            evidence_correct += 1

        elif evidence_decision.supported and not item.knowledge_expected:
            evidence_false_positive += 1

        elif not evidence_decision.supported and item.knowledge_expected:
            evidence_false_negative += 1

        print()
        print(
            f"[{index}/{total}]",
            item.query,
        )
        print(
            "knowledge_expected:",
            item.knowledge_expected,
        )
        print(
            "answer_passed:",
            answer_result.passed,
        )
        print(
            "retrieval_rank:",
            rank_result,
        )
        print(
            "evidence_supported:",
            evidence_decision.supported,
        )
        print(
            "evidence_reason:",
            evidence_decision.reason,
        )

    answer_pass_rate = answer_passed / total if total else 0.0

    in_scope_top1_hit_rate = (
        in_scope_top1_hits / in_scope_total if in_scope_total else 0.0
    )

    in_scope_topk_hit_rate = (
        in_scope_topk_hits / in_scope_total if in_scope_total else 0.0
    )

    in_scope_mean_expected_rank = (
        sum(in_scope_expected_ranks) / len(in_scope_expected_ranks)
        if in_scope_expected_ranks
        else None
    )

    out_of_scope_expected_miss_rate = (
        out_of_scope_expected_misses / out_of_scope_total if out_of_scope_total else 0.0
    )

    in_scope_mean_top1_score = (
        sum(in_scope_top1_scores) / len(in_scope_top1_scores)
        if in_scope_top1_scores
        else None
    )

    out_of_scope_mean_top1_score = (
        sum(out_of_scope_top1_scores) / len(out_of_scope_top1_scores)
        if out_of_scope_top1_scores
        else None
    )

    evidence_accuracy = evidence_correct / evidence_total if evidence_total else 0.0

    print()
    print("=" * 60)
    print("RAG Benchmark Summary")
    print("=" * 60)

    print("total:", total)
    print("answer_passed:", answer_passed)
    print(
        "answer_pass_rate:",
        answer_pass_rate,
    )

    print(
        "in_scope_total:",
        in_scope_total,
    )
    print(
        "in_scope_top1_hit_rate:",
        in_scope_top1_hit_rate,
    )
    print(
        "in_scope_topk_hit_rate:",
        in_scope_topk_hit_rate,
    )
    print(
        "in_scope_mean_expected_rank:",
        in_scope_mean_expected_rank,
    )

    print(
        "out_of_scope_total:",
        out_of_scope_total,
    )
    print(
        "out_of_scope_expected_miss_rate:",
        out_of_scope_expected_miss_rate,
    )

    print(
        "in_scope_top1_scores:",
        in_scope_top1_scores,
    )
    print(
        "out_of_scope_top1_scores:",
        out_of_scope_top1_scores,
    )

    print(
        "in_scope_mean_top1_score:",
        in_scope_mean_top1_score,
    )
    print(
        "out_of_scope_mean_top1_score:",
        out_of_scope_mean_top1_score,
    )

    print(
        "evidence_accuracy:",
        evidence_accuracy,
    )
    print(
        "evidence_false_positive:",
        evidence_false_positive,
    )
    print(
        "evidence_false_negative:",
        evidence_false_negative,
    )
    print(
        "evidence_total:",
        evidence_total,
    )


if __name__ == "__main__":
    run_benchmark()
