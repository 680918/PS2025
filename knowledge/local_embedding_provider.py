from sentence_transformers import SentenceTransformer

from knowledge.embedding_provider import (
    EmbeddingProvider,
)


class LocalEmbeddingProvider(
    EmbeddingProvider,
):
    def __init__(
        self,
        model=None,
        model_name="BAAI/bge-small-zh-v1.5",
    ):
        self.model = (
            model
            if model is not None
            else SentenceTransformer(
                model_name,
                device="cpu",
            )
        )

    def embed(self, text):
        vector = self.model.encode(
            text,
            normalize_embeddings=True,
        )

        return vector.tolist()