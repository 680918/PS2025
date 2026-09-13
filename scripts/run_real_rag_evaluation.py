from agent.controller import run_agent
from evaluation.rag_evaluator import (
    RAGEvaluationCase,
    evaluate_answer,
)
from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)
from knowledge.service import KnowledgeService


provider = LocalEmbeddingProvider()

knowledge_service = KnowledgeService(
    embedding_provider=provider,
)

knowledge_service.add_document(
    "data/knowledge/python_basics.txt",
    chunk_size=50,
)


query = "Python函数有什么作用？"

answer = run_agent(
    query,
    knowledge_service=knowledge_service,
)


case = RAGEvaluationCase(
    query=query,
    expected_keywords=[
        "封装",
        "参数",
        "返回",
    ],
)


evaluation = evaluate_answer(
    answer,
    case,
)


print()
print("Query:")
print(query)

print()
print("Agent answer:")
print(answer)

print()
print("Evaluation:")
print("passed:", evaluation.passed)
print(
    "matched_keywords:",
    evaluation.matched_keywords,
)
print(
    "missing_keywords:",
    evaluation.missing_keywords,
)