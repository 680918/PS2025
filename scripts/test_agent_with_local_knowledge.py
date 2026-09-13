from agent.controller import run_agent
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

results = knowledge_service.search(
    "Python函数有什么作用？",
    top_k=3,
)

print("Retrieved knowledge:")

for item in results:
    print(
        item.score,
        item.chunk.content,
    )


result = run_agent(
    "Python函数有什么作用？",
    knowledge_service=knowledge_service,
)

print()
print("Agent answer:")
print(result)