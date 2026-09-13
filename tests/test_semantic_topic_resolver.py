from knowledge.semantic_topic_resolver import (
    resolve_semantic_topics,
)


class FakeEmbeddingProvider:
    def embed(self, text):
        vectors = {
            "怎样把重复的代码整理成一个可以反复调用的模块？":
                [1.0, 0.0, 0.0],

            "封装一段可以重复使用的代码逻辑":
                [1.0, 0.0, 0.0],
            "把一段逻辑组织起来供以后调用":
                [1.0, 0.0, 0.0],
            "定义一个可以多次调用的代码单元":
                [1.0, 0.0, 0.0],

            "保存程序运行过程中的数据":
                [0.0, 1.0, 0.0],
            "存储计算产生的值供后续使用":
                [0.0, 1.0, 0.0],
            "给数据或计算结果一个名字并保存":
                [0.0, 1.0, 0.0],

            "重复执行同一个操作":
                [0.0, 0.0, 1.0],
            "让一段代码连续运行多次":
                [0.0, 0.0, 1.0],
            "对相同任务进行多次重复执行":
                [0.0, 0.0, 1.0],
        }

        return vectors[text]


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
            vectors = {
                "Python异常处理有什么作用？":
                    [0.5, 0.5, 0.5],

                "封装一段可以重复使用的代码逻辑":
                    [1.0, 0.0, 0.0],
                "把一段逻辑组织起来供以后调用":
                    [1.0, 0.0, 0.0],
                "定义一个可以多次调用的代码单元":
                    [1.0, 0.0, 0.0],

                "保存程序运行过程中的数据":
                    [0.0, 1.0, 0.0],
                "存储计算产生的值供后续使用":
                    [0.0, 1.0, 0.0],
                "给数据或计算结果一个名字并保存":
                    [0.0, 1.0, 0.0],

                "重复执行同一个操作":
                    [0.0, 0.0, 1.0],
                "让一段代码连续运行多次":
                    [0.0, 0.0, 1.0],
                "对相同任务进行多次重复执行":
                    [0.0, 0.0, 1.0],
            }

            return vectors[text]

    provider = UnknownEmbeddingProvider()

    matches = resolve_semantic_topics(
        query="Python异常处理有什么作用？",
        embedding_provider=provider,
    )

    assert matches == []

def test_ambiguous_match_should_be_rejected():
    class AmbiguousEmbeddingProvider:
        def embed(self, text):
            vectors = {
                "这是一个模糊的问题":
                    [1.0, 1.0, 0.0],

                "封装一段可以重复使用的代码逻辑":
                    [1.0, 0.9, 0.0],

                "把一段逻辑组织起来供以后调用":
                    [1.0, 0.9, 0.0],

                "定义一个可以多次调用的代码单元":
                    [1.0, 0.9, 0.0],

                "保存程序运行过程中的数据":
                    [0.9, 1.0, 0.0],

                "存储计算产生的值供后续使用":
                    [0.9, 1.0, 0.0],

                "给数据或计算结果一个名字并保存":
                    [0.9, 1.0, 0.0],

                "重复执行同一个操作":
                    [0.0, 0.0, 1.0],

                "让一段代码连续运行多次":
                    [0.0, 0.0, 1.0],

                "对相同任务进行多次重复执行":
                    [0.0, 0.0, 1.0],
            }

            return vectors[text]

    provider = AmbiguousEmbeddingProvider()

    matches = resolve_semantic_topics(
        query="这是一个模糊的问题",
        embedding_provider=provider,
        min_score=0.6,
        min_margin=0.08,
    )

    assert matches == []