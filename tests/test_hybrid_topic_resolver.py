from knowledge.hybrid_topic_resolver import (
    resolve_topics,
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
            vectors = {
                "有一段逻辑以后还要多次使用，应该怎么组织？": [1.0, 0.0, 0.0],
                "封装一段可以重复使用的代码逻辑": [1.0, 0.0, 0.0],
                "把一段逻辑组织起来供以后调用": [1.0, 0.0, 0.0],
                "定义一个可以多次调用的代码单元": [1.0, 0.0, 0.0],
                "保存程序运行过程中的数据": [0.0, 1.0, 0.0],
                "存储计算产生的值供后续使用": [0.0, 1.0, 0.0],
                "给数据或计算结果一个名字并保存": [0.0, 1.0, 0.0],
                "重复执行同一个操作": [0.0, 0.0, 1.0],
                "让一段代码连续运行多次": [0.0, 0.0, 1.0],
                "对相同任务进行多次重复执行": [0.0, 0.0, 1.0],
            }

            return vectors[text]

    provider = FakeEmbeddingProvider()

    topics = resolve_topics(
        query="有一段逻辑以后还要多次使用，应该怎么组织？",
        embedding_provider=provider,
    )

    assert topics == ["函数"]
