from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)


provider = LocalEmbeddingProvider()

vector = provider.embed("Python函数可以封装重复逻辑。")

print(
    "vector length:",
    len(vector),
)

print(
    "first 5 values:",
    vector[:5],
)

print(
    "vector type:",
    type(vector),
)
