from knowledge.evidence_policy import (
    EvidenceDecision,
    decide_evidence,
)
from knowledge.models import (
    KnowledgeChunk,
    RetrievalResult,
)
from knowledge.semantic_topic_resolver import TOPIC_PROTOTYPES
from knowledge.semantic_required_topic_resolver import (
    REQUIRED_TOPIC_PROTOTYPES,
)



class FakeEmbeddingProvider:
    def embed(self, text):
        if text == "有一段逻辑以后还要多次使用，应该怎么组织？":
            return [1.0, 0.0, 0.0]

        if text == "我知道变量和循环，但怎样避免重复写相同逻辑？":
            return [1.0, 0.0, 0.0]

        if text in TOPIC_PROTOTYPES["函数"]:
            return [1.0, 0.0, 0.0]

        if text in TOPIC_PROTOTYPES["变量"]:
            return [0.0, 1.0, 0.0]

        if text in TOPIC_PROTOTYPES["循环"]:
            return [0.0, 0.0, 1.0]

        if text in REQUIRED_TOPIC_PROTOTYPES["函数"]:
            return [1.0, 0.0, 0.0]

        if text in REQUIRED_TOPIC_PROTOTYPES["变量"]:
            return [0.0, 1.0, 0.0]

        if text in REQUIRED_TOPIC_PROTOTYPES["循环"]:
            return [0.0, 0.0, 1.0]

        raise KeyError(text)


def make_result(content, score=0.8):
    chunk = KnowledgeChunk(
        document_id="doc-1",
        content=content,
        chunk_index=0,
        source="test",
    )

    return RetrievalResult(
        chunk=chunk,
        score=score,
    )


def test_evidence_should_be_supported_when_chunk_answers_query():
    results = [
        make_result(
            "Python函数用于封装可以重复使用的逻辑。"
            "函数可以接收参数，也可以返回结果。"
        )
    ]

    decision = decide_evidence(
        query="Python函数有什么作用？",
        retrieval_results=results,
    )

    assert isinstance(
        decision,
        EvidenceDecision,
    )

    assert decision.supported is True
    assert len(decision.accepted_chunks) == 1


def test_evidence_should_not_be_supported_when_chunk_is_only_related():
    results = [
        make_result(
            "Python函数用于封装可以重复使用的逻辑。"
            "函数可以接收参数，也可以返回结果。",
            score=0.9,
        )
    ]

    decision = decide_evidence(
        query="Python类有什么作用？",
        retrieval_results=results,
    )

    assert decision.supported is False
    assert decision.accepted_chunks == []

def test_variable_evidence_should_be_supported():
    results = [
        make_result(
            "Python变量用于保存程序运行过程中的数据。"
        )
    ]

    decision = decide_evidence(
        query="Python变量有什么作用？",
        retrieval_results=results,
    )

    assert decision.supported is True
    assert len(decision.accepted_chunks) == 1


def test_loop_evidence_should_be_supported():
    results = [
        make_result(
            "Python循环用于重复执行一段代码。"
        )
    ]

    decision = decide_evidence(
        query="Python循环有什么作用？",
        retrieval_results=results,
    )

    assert decision.supported is True
    assert len(decision.accepted_chunks) == 1

def test_multi_topic_query_should_require_all_topics():
    results = [
        make_result(
            "Python函数用于封装可以重复使用的逻辑。"
        )
    ]

    decision = decide_evidence(
        query="函数和循环有什么区别？",
        retrieval_results=results,
    )

    assert decision.supported is False
    assert decision.accepted_chunks == []

def test_multi_topic_query_should_be_supported_when_all_topics_exist():
    results = [
        make_result(
            "Python函数用于封装可以重复使用的逻辑。"
        ),
        make_result(
            "Python循环用于重复执行一段代码。"
        ),
    ]

    decision = decide_evidence(
        query="函数和循环有什么区别？",
        retrieval_results=results,
    )

    assert decision.supported is True
    assert len(decision.accepted_chunks) == 2

def test_semantic_function_query_should_be_supported():
    results = [
        make_result(
            "Python函数用于封装可以重复使用的逻辑。"
            "函数可以接收参数，也可以返回结果。"
        )
    ]

    decision = decide_evidence(
        query="怎样把重复的代码整理成一个可以反复调用的模块？",
        retrieval_results=results,
    )

    assert decision.supported is True
    assert len(decision.accepted_chunks) == 1

def test_semantic_topic_should_be_supported_with_embedding_provider():
    results = [
        make_result(
            "Python函数用于封装可以重复使用的逻辑。"
            "函数可以接收参数，也可以返回结果。"
        )
    ]

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

            if text in REQUIRED_TOPIC_PROTOTYPES["函数"]:
                return [1.0, 0.0, 0.0]

            if text in REQUIRED_TOPIC_PROTOTYPES["变量"]:
                return [0.0, 1.0, 0.0]

            if text in REQUIRED_TOPIC_PROTOTYPES["循环"]:
                return [0.0, 0.0, 1.0]

            raise KeyError(text)

    decision = decide_evidence(
        query="有一段逻辑以后还要多次使用，应该怎么组织？",
        retrieval_results=results,
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert decision.supported is True
def test_context_topics_should_not_all_be_required():
    results = [
        make_result(
            "Python函数用于封装可以重复使用的逻辑。"
            "函数可以接收参数，也可以返回结果。"
        )
    ]

    decision = decide_evidence(
        query="我知道变量和循环，但怎样避免重复写相同逻辑？",
        retrieval_results=results,
        embedding_provider=FakeEmbeddingProvider(),
    )

    assert decision.supported is True