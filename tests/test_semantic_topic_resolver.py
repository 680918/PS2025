from knowledge.semantic_topic_resolver import (
    TOPIC_PROTOTYPES,
    resolve_semantic_topics,
)


class FakeEmbeddingProvider:
    def embed(self, text):
        if text == "怎样把重复的代码整理成一个可以反复调用的模块？":
            return [1.0, 0.0, 0.0]

        if text in TOPIC_PROTOTYPES["函数"]:
            return [1.0, 0.0, 0.0]

        if text in TOPIC_PROTOTYPES["变量"]:
            return [0.0, 1.0, 0.0]

        if text in TOPIC_PROTOTYPES["循环"]:
            return [0.0, 0.0, 1.0]

        raise KeyError(text)


def test_should_resolve_semantic_function_topic():
    provider = FakeEmbeddingProvider()

    matches = resolve_semantic_topics(
        query="怎样把重复的代码整理成一个可以反复调用的模块？",
        embedding_provider=provider,
    )

    assert len(matches) == 1
    assert matches[0].topic == "函数"


def test_unknown_topic_should_not_be_forced_to_known_topic():
    class UnknownEmbeddingProvider:
        def embed(self, text):
            if text == "Python异常处理有什么作用？":
                return [0.5, 0.5, 0.5]

            if text in TOPIC_PROTOTYPES["函数"]:
                return [1.0, 0.0, 0.0]

            if text in TOPIC_PROTOTYPES["变量"]:
                return [0.0, 1.0, 0.0]

            if text in TOPIC_PROTOTYPES["循环"]:
                return [0.0, 0.0, 1.0]

            raise KeyError(text)

    provider = UnknownEmbeddingProvider()

    matches = resolve_semantic_topics(
        query="Python异常处理有什么作用？",
        embedding_provider=provider,
    )

    assert matches == []


def test_ambiguous_match_should_be_rejected():
    class AmbiguousEmbeddingProvider:
        def embed(self, text):
            if text == "这是一个模糊的问题":
                return [1.0, 1.0, 0.0]

            if text in TOPIC_PROTOTYPES["函数"]:
                return [1.0, 0.9, 0.0]

            if text in TOPIC_PROTOTYPES["变量"]:
                return [0.9, 1.0, 0.0]

            if text in TOPIC_PROTOTYPES["循环"]:
                return [0.0, 0.0, 1.0]

            raise KeyError(text)

    provider = AmbiguousEmbeddingProvider()

    matches = resolve_semantic_topics(
        query="这是一个模糊的问题",
        embedding_provider=provider,
        min_score=0.6,
        min_margin=0.08,
    )

    assert matches == []
