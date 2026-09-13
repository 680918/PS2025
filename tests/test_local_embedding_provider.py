from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)


class FakeVector:
    def tolist(self):
        return [
            0.1,
            0.2,
            0.3,
        ]


class FakeModel:
    def encode(
        self,
        text,
        normalize_embeddings=True,
    ):
        assert text == "Python函数"
        assert normalize_embeddings is True

        return FakeVector()


def test_local_embedding_provider_should_return_list():
    provider = LocalEmbeddingProvider(
        model=FakeModel(),
    )

    vector = provider.embed("Python函数")

    assert vector == [
        0.1,
        0.2,
        0.3,
    ]
