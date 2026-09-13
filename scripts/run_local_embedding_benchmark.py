from evaluation.retrieval_benchmark import (
    build_python_baseline_benchmark,
)
from evaluation.retrieval_evaluator import (
    RetrievalEvaluationCase,
    evaluate_retrieval,
)
from knowledge.embedding_retriever import (
    retrieve_chunks_by_embedding,
)
from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)
from knowledge.models import KnowledgeChunk
from knowledge.store import KnowledgeStore


store = KnowledgeStore()

store.add_many(
    [
        KnowledgeChunk(
            document_id="python",
            content="Python函数可以封装重复逻辑并接受参数。",
            chunk_index=0,
            source="python.txt",
            id="function-chunk",
        ),
        KnowledgeChunk(
            document_id="python",
            content="Python变量用于保存程序运行中的数据。",
            chunk_index=1,
            source="python.txt",
            id="variable-chunk",
        ),
        KnowledgeChunk(
            document_id="python",
            content="Python循环可以重复执行一段代码。",
            chunk_index=2,
            source="python.txt",
            id="loop-chunk",
        ),
    ]
)

provider = LocalEmbeddingProvider()

benchmark_items = build_python_baseline_benchmark()

cases = [
    RetrievalEvaluationCase(
        query=item.query,
        expected_chunk_id=(item.expected_chunk_id),
    )
    for item in benchmark_items
]


def retriever(query, k):
    return retrieve_chunks_by_embedding(
        query,
        store,
        provider,
        top_k=k,
    )


evaluation = evaluate_retrieval(
    retriever,
    cases,
    k=1,
)

print()
print("total:", evaluation["total"])
print("hits:", evaluation["hits"])
print(
    "hit_rate:",
    evaluation["hit_rate"],
)

for case in evaluation["cases"]:
    print(
        case.query,
        "=>",
        case.retrieved_chunk_ids,
        "hit=",
        case.hit,
    )
