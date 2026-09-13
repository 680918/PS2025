from knowledge.embedding_provider import (
    EmbeddingProvider,
)


class OpenAIEmbeddingProvider(
    EmbeddingProvider,
):
    def __init__(
        self,
        client,
        model,
    ):
        self.client = client
        self.model = model

    def embed(self, text):
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )

        return response.data[0].embedding
