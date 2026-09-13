from knowledge.models import KnowledgeChunk
from knowledge.retriever import retrieve_chunks
from knowledge.store import KnowledgeStore
from knowledge.retriever import (
    extract_query_terms,
    score_chunk,
)


def make_chunk(
    document_id,
    content,
    chunk_index,
):
    return KnowledgeChunk(
        document_id=document_id,
        content=content,
        chunk_index=chunk_index,
        source="test.txt",
    )


def test_retrieve_matching_chunk():
    store = KnowledgeStore()

    store.add_many(
        [
            make_chunk(
                "doc-1",
                "Python 函数可以封装重复逻辑。",
                0,
            ),
            make_chunk(
                "doc-1",
                "系统思维强调反馈回路。",
                1,
            ),
        ]
    )

    results = retrieve_chunks(
        "Python 函数",
        store,
    )

    assert len(results) == 1
    assert "Python" in results[0].chunk.content


def test_retrieve_should_rank_more_matches_first():
    store = KnowledgeStore()

    chunk1 = make_chunk(
        "doc-1",
        "Python 是编程语言。",
        0,
    )

    chunk2 = make_chunk(
        "doc-1",
        "Python 函数是 Python 学习的重要内容。",
        1,
    )

    store.add_many([chunk1, chunk2])

    results = retrieve_chunks(
        "Python 函数",
        store,
    )

    assert results[0].chunk == chunk2


def test_retrieve_respects_top_k():
    store = KnowledgeStore()

    for index in range(5):
        store.add(
            make_chunk(
                "doc-1",
                f"Python 学习资料 {index}",
                index,
            )
        )

    results = retrieve_chunks(
        "Python",
        store,
        top_k=2,
    )

    assert len(results) == 2


def test_retrieve_no_match_returns_empty_list():
    store = KnowledgeStore()

    store.add(
        make_chunk(
            "doc-1",
            "系统思维强调反馈回路。",
            0,
        )
    )

    results = retrieve_chunks(
        "Python",
        store,
    )

    assert results == []


def test_retrieve_empty_query_returns_empty_list():
    store = KnowledgeStore()

    results = retrieve_chunks(
        "",
        store,
    )

    assert results == []


def test_retrieve_chinese_natural_question():
    store = KnowledgeStore()

    store.add(
        make_chunk(
            "doc-1",
            "Python函数可以封装重复逻辑。",
            0,
        )
    )

    results = retrieve_chunks(
        "Python函数是什么？",
        store,
    )

    assert len(results) == 1
    assert "Python函数" in results[0].chunk.content


def test_score_chunk_should_prefer_phrase_match():
    query = "Python 函数"

    query_terms = extract_query_terms(query)

    score1 = score_chunk(
        query,
        query_terms,
        "Python函数可以封装逻辑。",
    )

    score2 = score_chunk(
        query,
        query_terms,
        "Python是一门语言，函数是一种结构。",
    )

    assert score1 > score2


def test_score_chunk_should_reward_more_term_matches():
    query = "Python 函数 参数"

    query_terms = extract_query_terms(query)

    score1 = score_chunk(
        query,
        query_terms,
        "Python函数可以接受参数。",
    )

    score2 = score_chunk(
        query,
        query_terms,
        "Python是一门语言。",
    )

    assert score1 > score2


def test_retrieve_should_filter_low_score_results():
    store = KnowledgeStore()

    store.add_many(
        [
            make_chunk(
                "doc-1",
                "Python函数可以接受参数。",
                0,
            ),
            make_chunk(
                "doc-2",
                "Python是一门语言。",
                0,
            ),
        ]
    )

    results = retrieve_chunks(
        "Python 函数 参数",
        store,
        min_score=2.0,
    )

    assert len(results) == 1
    assert "函数" in results[0].chunk.content


def test_retrieve_should_allow_custom_min_score():
    store = KnowledgeStore()

    store.add(
        make_chunk(
            "doc-1",
            "Python是一门语言。",
            0,
        )
    )

    results = retrieve_chunks(
        "Python 函数",
        store,
        min_score=1.0,
    )

    assert len(results) == 1


def test_retrieve_should_return_score():
    store = KnowledgeStore()

    store.add(
        make_chunk(
            "doc-1",
            "Python函数可以接受参数。",
            0,
        )
    )

    results = retrieve_chunks(
        "Python 函数",
        store,
    )

    assert len(results) == 1
    assert results[0].score > 0
    assert results[0].chunk.content == ("Python函数可以接受参数。")


def test_extract_query_terms_should_remove_question_patterns():
    assert "python函数" in extract_query_terms("Python函数有什么作用？")

    assert "python变量" in extract_query_terms("Python变量是干什么的？")

    assert "python循环" in extract_query_terms("Python循环有什么作用？")
