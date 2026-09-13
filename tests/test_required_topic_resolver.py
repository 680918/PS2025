from knowledge.required_topic_resolver import (
    resolve_required_topics,
)
from knowledge.semantic_required_topic_resolver import (
    REQUIRED_TOPIC_PROTOTYPES,
)

class FakeEmbeddingProvider:
    def embed(self, text):
        function_queries = {
            "我知道变量和循环，但怎样避免重复写相同逻辑？",
            "变量和循环我已经了解了，现在怎样减少重复代码？",
            "先不讨论变量和循环，我现在想知道怎么复用一段逻辑。",
        }

        if text in function_queries:
            return [1.0, 0.0, 0.0]

        if text in REQUIRED_TOPIC_PROTOTYPES["函数"]:
            return [1.0, 0.0, 0.0]

        if text in REQUIRED_TOPIC_PROTOTYPES["变量"]:
            return [0.0, 1.0, 0.0]

        if text in REQUIRED_TOPIC_PROTOTYPES["循环"]:
            return [0.0, 0.0, 1.0]

        raise KeyError(text)

def test_single_topic_should_remain_required():
    result = resolve_required_topics(
        query="Python函数有什么作用？",
        mentioned_topics=["函数"],
    )

    assert result == ["函数"]


def test_comparison_topics_should_all_be_required():
    result = resolve_required_topics(
        query="变量和循环有什么区别？",
        mentioned_topics=["变量", "循环"],
    )

    assert set(result) == {"变量", "循环"}


def test_context_topics_should_not_all_be_required():
    result = resolve_required_topics(
        query="我知道变量和循环，但怎样避免重复写相同逻辑？",
        mentioned_topics=["变量", "循环", "函数"],
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert result == ["函数"]

def test_context_topics_generalization_1():
    result = resolve_required_topics(
        query="变量和循环我已经了解了，现在怎样减少重复代码？",
        mentioned_topics=["变量", "循环", "函数"],
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert result == ["函数"]


def test_context_topics_generalization_2():
    result = resolve_required_topics(
        query="先不讨论变量和循环，我现在想知道怎么复用一段逻辑。",
        mentioned_topics=["变量", "循环", "函数"],
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert result == ["函数"]

def test_focused_question_should_use_semantic_resolution():
    result = resolve_required_topics(
        query="变量和循环我已经了解了，现在怎样减少重复代码？",
        mentioned_topics=["变量", "循环", "函数"],
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert result == ["函数"]

def test_comparison_should_keep_all_mentioned_topics_with_embedding_provider():
    result = resolve_required_topics(
        query="变量和循环有什么区别？",
        mentioned_topics=["变量", "循环"],
        embedding_provider=None,
    )

    assert set(result) == {"变量", "循环"}

def test_focused_question_should_infer_required_topic_not_explicitly_mentioned():
    result = resolve_required_topics(
        query="我知道变量和循环，但怎样避免重复写相同逻辑？",
        mentioned_topics=["变量", "循环"],
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert result == ["函数"]

def test_no_mentioned_topics_should_not_infer_required_topic():
    result = resolve_required_topics(
        query="数据库事务应该怎么处理？",
        mentioned_topics=[],
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert result == []