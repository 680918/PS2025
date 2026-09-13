from knowledge.topic_resolver import (
    resolve_query_topics,
)


def test_rule_resolver_should_not_guess_semantic_function_topic():
    topics = resolve_query_topics("有一段逻辑以后还要多次使用，应该怎么组织？")

    assert topics == []


def test_rule_resolver_should_not_guess_semantic_variable_topic():
    topics = resolve_query_topics("程序算出来的值以后还要继续使用，应该放到哪里？")

    assert topics == []


def test_rule_resolver_should_not_guess_semantic_loop_topic():
    topics = resolve_query_topics("同样的操作需要反复做几十次，有什么合适的方法？")

    assert topics == []


def test_unknown_topic_should_not_be_forced_into_known_topics():
    topics = resolve_query_topics("Python异常处理有什么作用？")

    assert topics == []
