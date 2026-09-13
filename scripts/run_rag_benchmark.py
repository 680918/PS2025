from agent.controller import run_agent
from evaluation.rag_benchmark import (
    build_python_rag_benchmark,
)

from evaluation.rag_evaluator import (
    RAGEvaluationCase,
    evaluate_answer,
)
from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)
from knowledge.service import KnowledgeService

from evaluation.rag_diagnosis import (
    diagnose_rag_case,
    evaluate_retrieval_rank,
)
from knowledge.evidence_policy import decide_evidence


embedding_provider = LocalEmbeddingProvider()

knowledge_service = KnowledgeService(
    embedding_provider=embedding_provider,
)

knowledge_service.add_document(
    "data/knowledge/python_basics.txt",
    chunk_size=50,
)


benchmark = build_python_rag_benchmark()

total = len(benchmark)
passed = 0

top1_hits = 0
topk_hits = 0
expected_ranks = []

in_scope_total = 0
in_scope_top1_hits = 0
in_scope_topk_hits = 0
in_scope_expected_ranks = []

out_of_scope_total = 0
out_of_scope_expected_misses = 0

in_scope_top1_scores = []
out_of_scope_top1_scores = []

evidence_total = 0
evidence_correct = 0
evidence_false_positive = 0
evidence_false_negative = 0

for item in benchmark:

    # 1. 先单独执行 Retrieval
    retrieval_results = knowledge_service.search(
        item.query,
        top_k=3,
    )

    evidence_decision = decide_evidence(
        query=item.query,
        retrieval_results=retrieval_results,
        embedding_provider=embedding_provider,
    )

    evidence_total += 1

    expected_supported = item.knowledge_expected

    if evidence_decision.supported == expected_supported:
        evidence_correct += 1

    elif (
        evidence_decision.supported
        and not expected_supported
    ):
        evidence_false_positive += 1

    elif (
        not evidence_decision.supported
        and expected_supported
    ):
        evidence_false_negative += 1

     # ===== 第4步放这里 =====

    print("\nEvidence Policy:")
    print(
        "supported:",
        evidence_decision.supported,
    )
    print(
        "expected_supported:",
        expected_supported,
    )
    print(
        "accepted_chunks:",
        len(
            evidence_decision.accepted_chunks
        ),
    )
    print(
        "reason:",
        evidence_decision.reason,
    )

    top1_score = (
        retrieval_results[0].score
        if retrieval_results
        else None
    )

    retrieval_rank = evaluate_retrieval_rank(
        retrieval_results,
        item.expected_retrieval_keyword,
    )

    if item.knowledge_expected:
        in_scope_total += 1

        if top1_score is not None:
            in_scope_top1_scores.append(top1_score)

        if retrieval_rank["top1_hit"]:
            in_scope_top1_hits += 1

        if retrieval_rank["topk_hit"]:
            in_scope_topk_hits += 1

        if retrieval_rank["expected_rank"] is not None:
            in_scope_expected_ranks.append(
                retrieval_rank["expected_rank"]
            )

    else:
        out_of_scope_total += 1

        if top1_score is not None:
            out_of_scope_top1_scores.append(top1_score)

        if not retrieval_rank["topk_hit"]:
            out_of_scope_expected_misses += 1

    # 2. 判断 Retrieval 是否找到了正确主题
    if item.knowledge_expected:
        retrieval_ok = retrieval_rank[
            "topk_hit"
        ]
    else:
        retrieval_ok = not retrieval_rank[
            "topk_hit"
        ]

    # 3. 运行真实 Agent
    answer = run_agent(
        item.query,
        knowledge_service=knowledge_service,
    )

    # 4. 评估最终回答
    case = RAGEvaluationCase(
        query=item.query,
        expected_keywords=item.expected_keywords,
        expected_boundary_keywords=(
            item.expected_boundary_keywords
        ),
    )

    evaluation = evaluate_answer(
        answer,
        case,
    )

    if evaluation.passed:
        passed += 1

    print()
    print("Retrieval Diagnosis:")
    print(
        "top1_hit:",
        retrieval_rank["top1_hit"],
    )
    print(
        "topk_hit:",
        retrieval_rank["topk_hit"],
    )
    print(
        "expected_rank:",
        retrieval_rank["expected_rank"],
    )

    # 5. 诊断失败发生在哪一层
    diagnosis = diagnose_rag_case(
        retrieved_chunk_ids=(
            ["expected"]
            if retrieval_ok
            else []
        ),
        expected_chunk_id="expected",
        answer_passed=evaluation.passed,
    )

    # 6. 输出结果
    print()
    print("=" * 60)

    print("Query:")
    print(item.query)

    print()
    print("Retrieval:")

    for rank, result in enumerate(
        retrieval_results,
        start=1,
    ):
        print(
            f"rank={rank}",
            f"score={result.score:.4f}",
            f"chunk_id={result.chunk.id}",
        )
        print(
            result.chunk.content
        )

    print()
    print("Answer:")
    print(answer)

    print()
    print("Evaluation:")
    print(
        "passed:",
        evaluation.passed,
    )
    print(
        "matched:",
        evaluation.matched_keywords,
    )
    print(
        "missing:",
        evaluation.missing_keywords,
    )

    print()
    print("Diagnosis:")
    print(
        "retrieval_ok:",
        diagnosis.retrieval_ok,
    )
    print(
        "answer_ok:",
        diagnosis.answer_ok,
    )
    print(
        "failure_stage:",
        diagnosis.failure_stage,
    )


print()
print("=" * 60)
print("RAG Benchmark Summary")

print(
    "total:",
    total,
)

print(
    "answer_passed:",
    passed,
)

print(
    "answer_pass_rate:",
    passed / total if total else 0.0,
)

print(
    "in_scope_total:",
    in_scope_total,
)

print(
    "in_scope_top1_hit_rate:",
    (
        in_scope_top1_hits
        / in_scope_total
        if in_scope_total
        else 0.0
    ),
)

print(
    "in_scope_topk_hit_rate:",
    (
        in_scope_topk_hits
        / in_scope_total
        if in_scope_total
        else 0.0
    ),
)

mean_expected_rank = (
    sum(in_scope_expected_ranks)
    / len(in_scope_expected_ranks)
    if in_scope_expected_ranks
    else None
)

print(
    "in_scope_mean_expected_rank:",
    mean_expected_rank,
)

print(
    "out_of_scope_total:",
    out_of_scope_total,
)

print(
    "out_of_scope_expected_miss_rate:",
    out_of_scope_expected_misses / out_of_scope_total
    if out_of_scope_total
    else 0.0,
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
    sum(in_scope_top1_scores)
    / len(in_scope_top1_scores)
    if in_scope_top1_scores
    else None,
)

print(
    "out_of_scope_mean_top1_score:",
    sum(out_of_scope_top1_scores)
    / len(out_of_scope_top1_scores)
    if out_of_scope_top1_scores
    else None,
)

print(
    "evidence_accuracy:",
    evidence_correct / evidence_total
    if evidence_total
    else 0.0,
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