from knowledge.topic_resolver import (
    resolve_query_topics,
)


def test_should_resolve_literal_function_topic():
    topics = resolve_query_topics(
        "Python函数有什么作用？"
    )

    assert topics == ["函数"]


def test_should_resolve_literal_variable_topic():
    topics = resolve_query_topics(
        "Python变量有什么作用？"
    )

    assert topics == ["变量"]


def test_should_resolve_literal_loop_topic():
    topics = resolve_query_topics(
        "Python循环有什么作用？"
    )

    assert topics == ["循环"]


def test_should_resolve_multiple_topics():
    topics = resolve_query_topics(
        "函数和循环有什么区别？"
    )

    assert topics == [
        "函数",
        "循环",
    ]


def test_should_resolve_semantic_function_topic():
    topics = resolve_query_topics(
        "怎样把重复的代码整理成一个可以反复调用的模块？"
    )

    assert topics == ["函数"]


def test_should_return_empty_for_unknown_topic():
    topics = resolve_query_topics(
        "Python类有什么作用？"
    )

    assert topics == []

def test_should_resolve_semantic_variable_topic():
    topics = resolve_query_topics(
        "程序运行过程中产生的数据应该放在哪里？"
    )

    assert topics == ["变量"]


def test_should_resolve_semantic_loop_topic():
    topics = resolve_query_topics(
        "如果一段代码要连续执行很多次，应该怎么办？"
    )

    assert topics == ["循环"]