from knowledge.openai_embedding_provider import (
    OpenAIEmbeddingProvider,
)


class FakeEmbeddingData:
    def __init__(self):
        self.embedding = [
            0.1,
            0.2,
            0.3,
        ]


class FakeEmbeddingResponse:
    def __init__(self):
        self.data = [FakeEmbeddingData()]


class FakeEmbeddings:
    def create(
        self,
        model,
        input,
    ):
        assert model == "test-model"
        assert input == "Python函数"

        return FakeEmbeddingResponse()


class FakeClient:
    def __init__(self):
        self.embeddings = FakeEmbeddings()


def test_openai_embedding_provider_should_return_vector():
    provider = OpenAIEmbeddingProvider(
        client=FakeClient(),
        model="test-model",
    )

    vector = provider.embed("Python函数")

    assert vector == [
        0.1,
        0.2,
        0.3,
    ]
