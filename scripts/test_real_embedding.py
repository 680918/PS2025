from openai import OpenAI

from knowledge.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)


client = OpenAI()

provider = OpenAIEmbeddingProvider(
    client=client,
    model="text-embedding-3-small",
)

vector = provider.embed(
    "Python函数可以封装重复逻辑。"
)

print("vector length:", len(vector))
print("first 5 values:", vector[:5])