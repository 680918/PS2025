from knowledge.semantic_required_topic_resolver import (
    resolve_semantic_required_topics,
)
from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)


class FakeEmbeddingProvider:
    def embed(self, text):
        vectors = {
            # query
            "变量和循环我已经了解了，现在怎样减少重复代码？": [
                1.0,
                0.0,
                0.0,
            ],

            # 函数 prototypes
            "怎样减少重复代码": [1.0, 0.0, 0.0],
            "怎样复用一段逻辑": [1.0, 0.0, 0.0],
            "怎样把重复逻辑封装起来重复调用": [1.0, 0.0, 0.0],
            "一段逻辑以后还要使用应该怎么组织": [1.0, 0.0, 0.0],

            # 变量 prototypes
            "怎样保存程序中的数据": [0.0, 1.0, 0.0],
            "计算结果应该存放在哪里": [0.0, 1.0, 0.0],
            "怎样保存一个值供后续使用": [0.0, 1.0, 0.0],
            "程序运行中的数据应该怎么保存": [0.0, 1.0, 0.0],

            # 循环 prototypes
            "怎样重复执行一段代码": [0.0, 0.0, 1.0],
            "同一个操作需要执行很多次怎么办": [0.0, 0.0, 1.0],
            "怎样让程序反复执行相同操作": [0.0, 0.0, 1.0],
            "代码需要连续运行多次应该怎么做": [0.0, 0.0, 1.0],
        }

        return vectors[text]


def test_semantic_required_topic_should_select_function():
    result = resolve_semantic_required_topics(
        query="变量和循环我已经了解了，现在怎样减少重复代码？",
        mentioned_topics=["变量", "循环", "函数"],
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert result == ["函数"]

def test_comparison_should_keep_multiple_required_topics():
    class ComparisonEmbeddingProvider:
        def embed(self, text):
            vectors = {
                "变量和循环有什么区别？": [
                    1.0,
                    1.0,
                    0.0,
                ],

                # 变量 prototypes
                "怎样保存程序中的数据": [
                    1.0,
                    0.0,
                    0.0,
                ],
                "计算结果应该存放在哪里": [
                    1.0,
                    0.0,
                    0.0,
                ],
                "怎样保存一个值供后续使用": [
                    1.0,
                    0.0,
                    0.0,
                ],
                "程序运行中的数据应该怎么保存": [
                    1.0,
                    0.0,
                    0.0,
                ],

                # 循环 prototypes
                "怎样重复执行一段代码": [
                    0.0,
                    1.0,
                    0.0,
                ],
                "同一个操作需要执行很多次怎么办": [
                    0.0,
                    1.0,
                    0.0,
                ],
                "怎样让程序反复执行相同操作": [
                    0.0,
                    1.0,
                    0.0,
                ],
                "代码需要连续运行多次应该怎么做": [
                    0.0,
                    1.0,
                    0.0,
                ],
            }

            return vectors[text]

    result = resolve_semantic_required_topics(
        query="变量和循环有什么区别？",
        mentioned_topics=["变量", "循环"],
        embedding_provider=ComparisonEmbeddingProvider(),
    )

    assert set(result) == {"变量", "循环"}


def test_real_embedding_should_ignore_context_topics():
    provider = LocalEmbeddingProvider()

    result = resolve_semantic_required_topics(
        query="变量和循环我已经了解了，现在怎样减少重复代码？",
        mentioned_topics=["变量", "循环", "函数"],
        embedding_provider=provider,
    )

    assert result == ["函数"]