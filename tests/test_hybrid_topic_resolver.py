from knowledge.hybrid_topic_resolver import (
    resolve_topics,
)
from knowledge.semantic_topic_resolver import (
    TOPIC_PROTOTYPES,
)


def test_should_use_rule_resolver_first():
    topics = resolve_topics(
        query="Python函数有什么作用？",
        embedding_provider=None,
    )

    assert topics == ["函数"]


def test_should_fallback_to_semantic_resolver():
    class FakeEmbeddingProvider:
        def embed(self, text):
            if text == "有一段逻辑以后还要多次使用，应该怎么组织？":
                return [1.0, 0.0, 0.0]

            if text in TOPIC_PROTOTYPES["函数"]:
                return [1.0, 0.0, 0.0]

            if text in TOPIC_PROTOTYPES["变量"]:
                return [0.0, 1.0, 0.0]

            if text in TOPIC_PROTOTYPES["循环"]:
                return [0.0, 0.0, 1.0]

            raise KeyError(text)

    provider = FakeEmbeddingProvider()

    topics = resolve_topics(
        query="有一段逻辑以后还要多次使用，应该怎么组织？",
        embedding_provider=provider,
    )

    assert topics == ["函数"]
