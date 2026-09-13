from knowledge.semantic_topic_resolver import (
    resolve_semantic_topics,
)
from knowledge.local_embedding_provider import (
    LocalEmbeddingProvider,
)


provider = LocalEmbeddingProvider()


def resolve_one(query):
    matches = resolve_semantic_topics(
        query=query,
        embedding_provider=provider,
    )

    if not matches:
        return None

    return matches[0].topic


def test_function_paraphrase_1():
    assert resolve_one("一段代码以后可能重复使用，应该怎么组织？") == "函数"


def test_function_paraphrase_2():
    assert resolve_one("怎样把一段逻辑包装起来，以后直接调用？") == "函数"


def test_variable_paraphrase_1():
    assert resolve_one("程序计算得到的结果，怎样保存下来以后继续用？") == "变量"


def test_variable_paraphrase_2():
    assert resolve_one("运行过程中有个值需要暂时记住，应该用什么？") == "变量"


def test_loop_paraphrase_1():
    assert resolve_one("同一段操作需要执行很多遍，应该怎么处理？") == "循环"


def test_loop_paraphrase_2():
    assert resolve_one("怎样让程序重复做同一件事情？") == "循环"


def test_exception_should_be_rejected():
    assert resolve_one("Python异常处理应该怎么写？") is None


def test_class_should_be_rejected():
    assert resolve_one("Python类和对象有什么关系？") is None


def test_decorator_should_be_rejected():
    assert resolve_one("Python装饰器为什么有用？") is None


def test_file_should_be_rejected():
    assert resolve_one("Python怎样读取文本文件？") is None


def test_database_should_be_rejected():
    assert resolve_one("数据库索引有什么作用？") is None


def test_network_should_be_rejected():
    assert resolve_one("HTTP请求是怎么工作的？") is None
