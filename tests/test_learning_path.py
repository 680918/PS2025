from planning.learning_path import get_next_topic


def test_python_function_should_advance_to_exception_handling():
    next_topic = get_next_topic("Python函数")

    assert next_topic == "Python异常处理"


def test_unknown_topic_should_return_none():
    next_topic = get_next_topic("不存在的主题")

    assert next_topic is None


def test_last_topic_should_return_none():
    next_topic = get_next_topic("Python面向对象基础")

    assert next_topic is None
