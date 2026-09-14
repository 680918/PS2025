import pytest

from knowledge.evidence_policy import decide_evidence
from knowledge.local_embedding_provider import LocalEmbeddingProvider
from knowledge.models import KnowledgeChunk, RetrievalResult


@pytest.fixture(scope="module")
def embedding_provider():
    return LocalEmbeddingProvider()


@pytest.fixture
def retrieval_results():
    chunks = [
        KnowledgeChunk(
            document_id="python",
            content="Python函数用于封装可以重复使用的逻辑。",
            chunk_index=0,
            source="python.txt",
            id="function-chunk",
        ),
        KnowledgeChunk(
            document_id="python",
            content="Python变量用于保存程序运行过程中的数据。",
            chunk_index=1,
            source="python.txt",
            id="variable-chunk",
        ),
        KnowledgeChunk(
            document_id="python",
            content="Python循环用于重复执行一段代码。",
            chunk_index=2,
            source="python.txt",
            id="loop-chunk",
        ),
    ]

    return [RetrievalResult(chunk=chunk, score=0.8) for chunk in chunks]


@pytest.mark.parametrize(
    "query, expected_supported",
    [
        # --------------------------------------------------
        # 1. focused + context interference
        # --------------------------------------------------
        (
            "变量和循环我都会了，如果一段代码以后还想反复使用，该怎么办？",
            True,
        ),
        (
            "循环我已经知道怎么用了，现在想把一段逻辑放起来以后继续调用。",
            True,
        ),
        (
            "先不考虑变量，我写好的处理步骤以后还会用很多次，该怎么组织？",
            True,
        ),
        (
            "我已经学过循环和变量，现在想解决代码复用的问题。",
            True,
        ),
        (
            "数据保存我懂了，但重复出现的一整段逻辑应该怎么处理？",
            True,
        ),
        # --------------------------------------------------
        # 2. comparison
        # --------------------------------------------------
        (
            "保存数据和重复执行代码分别应该用什么？",
            True,
        ),
        (
            "变量和循环解决的问题有什么不同？",
            True,
        ),
        (
            "函数和循环分别适合解决什么问题？",
            True,
        ),
        (
            "保存一个结果与反复执行一个操作，在Python里应该分别怎么做？",
            True,
        ),
        (
            "函数、变量和循环各自负责什么？",
            True,
        ),
        # --------------------------------------------------
        # 3. implicit intent
        # --------------------------------------------------
        (
            "有一段处理逻辑很多地方都要调用，应该怎么组织？",
            True,
        ),
        (
            "同样的一组处理步骤在程序不同位置都会使用，怎样避免到处重写？",
            True,
        ),
        (
            "某段代码以后还要反复拿出来使用，有没有更好的组织方式？",
            True,
        ),
        (
            "我不想复制粘贴同一套代码，应该怎么复用已有逻辑？",
            True,
        ),
        (
            "怎样把经常使用的一段处理过程整理成可以再次使用的东西？",
            True,
        ),
        # --------------------------------------------------
        # 4. out of scope
        # --------------------------------------------------
        (
            "数据库事务回滚应该怎么处理？",
            False,
        ),
        (
            "Python装饰器的执行顺序是什么？",
            False,
        ),
        (
            "生成器为什么可以节省内存？",
            False,
        ),
        (
            "多线程中的死锁应该怎样避免？",
            False,
        ),
        (
            "HTTP请求超时后应该如何重试？",
            False,
        ),
        # --------------------------------------------------
        # 5. negation / context exclusion
        # --------------------------------------------------
        (
            "我不是想保存数据，而是想让同一段操作执行很多遍。",
            True,
        ),
        (
            "我说的不是循环执行，我是想以后还能再次调用这一段处理逻辑。",
            True,
        ),
        (
            "现在先不讨论函数，我只想知道怎样保存计算结果。",
            True,
        ),
        (
            "不是要把值保存下来，而是需要重复执行同样的步骤。",
            True,
        ),
        (
            "我已经不关心变量了，现在的问题是代码怎样重复利用。",
            True,
        ),
        # --------------------------------------------------
        # 6. ambiguous
        # --------------------------------------------------
        (
            "这种代码应该怎么处理？",
            False,
        ),
        (
            "这个东西有什么用？",
            False,
        ),
        (
            "我下一步应该怎么办？",
            False,
        ),
        (
            "这两种方式哪个好？",
            False,
        ),
        (
            "这里应该怎么写？",
            False,
        ),
    ],
)
def test_shadow_generalization(
    query,
    expected_supported,
    retrieval_results,
    embedding_provider,
):
    decision = decide_evidence(
        query=query,
        retrieval_results=retrieval_results,
        embedding_provider=embedding_provider,
    )

    assert decision.supported is expected_supported


@pytest.mark.parametrize(
    "query",
    [
        "写过的一段处理步骤以后还想继续用，该怎么组织？",
        "同一套处理逻辑以后还会反复调用，应该怎么设计？",
        "一段已经写好的逻辑想在其他地方继续使用怎么办？",
        "很多地方都需要用到相同的处理过程，应该如何整理？",
        "怎样把一组操作变成以后还能继续使用的代码单元？",
        "同样的处理流程不想重复写很多遍，该怎么办？",
    ],
)
def test_function_reuse_generalization(
    query,
    retrieval_results,
    embedding_provider,
):
    decision = decide_evidence(
        query=query,
        retrieval_results=retrieval_results,
        embedding_provider=embedding_provider,
    )

    assert decision.supported is True


@pytest.mark.parametrize(
    "query",
    [
        "我不想每次都重新写同一套处理步骤。",
    ],
)
def test_borderline_shadow_cases(
    query,
    retrieval_results,
    embedding_provider,
):
    decision = decide_evidence(
        query=query,
        retrieval_results=retrieval_results,
        embedding_provider=embedding_provider,
    )

    print(
        "\nBorderline Query:",
        query,
    )
    print(
        "Supported:",
        decision.supported,
    )
    print(
        "Reason:",
        decision.reason,
    )
