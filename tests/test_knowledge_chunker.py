import pytest

from knowledge.models import KnowledgeDocument
from knowledge.chunker import (
    chunk_document,
    split_sentences,
    build_sentence_chunks,
    add_overlap,
)

def test_chunk_short_document():
    document = KnowledgeDocument(
        title="test",
        content="abcdef",
        source="test.txt",
    )

    chunks = chunk_document(
        document,
        chunk_size=10,
    )

    assert len(chunks) == 1
    assert chunks[0].content == "abcdef"
    assert chunks[0].chunk_index == 0
    assert chunks[0].document_id == document.id


def test_chunk_long_document():
    document = KnowledgeDocument(
        title="test",
        content="abcdefghij",
        source="test.txt",
    )

    chunks = chunk_document(
        document,
        chunk_size=4,
    )

    assert len(chunks) == 3

    assert chunks[0].content == "abcd"
    assert chunks[1].content == "efgh"
    assert chunks[2].content == "ij"

    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[2].chunk_index == 2


def test_chunk_empty_document():
    document = KnowledgeDocument(
        title="test",
        content="",
        source="test.txt",
    )

    chunks = chunk_document(document)

    assert chunks == []


def test_chunk_document_rejects_invalid_chunk_size():
    document = KnowledgeDocument(
        title="test",
        content="abcdef",
        source="test.txt",
    )

    with pytest.raises(ValueError):
        chunk_document(
            document,
            chunk_size=0,
        )

def test_chunk_document_with_overlap():
    document = KnowledgeDocument(
        title="test",
        content="abcdefghij",
        source="test.txt",
    )

    chunks = chunk_document(
        document,
        chunk_size=6,
        overlap=2,
    )

    assert len(chunks) == 2
    assert chunks[0].content == "abcdef"
    assert chunks[1].content == "efghij"

def test_chunk_document_rejects_negative_overlap():
    document = KnowledgeDocument(
        title="test",
        content="abcdef",
        source="test.txt",
    )

    with pytest.raises(ValueError):
        chunk_document(
            document,
            chunk_size=6,
            overlap=-1,
        )


def test_chunk_document_rejects_overlap_equal_to_chunk_size():
    document = KnowledgeDocument(
        title="test",
        content="abcdef",
        source="test.txt",
    )

    with pytest.raises(ValueError):
        chunk_document(
            document,
            chunk_size=6,
            overlap=6,
        )

def test_split_sentences_should_keep_sentence_boundaries():
    text = (
        "Python函数可以封装逻辑。"
        "函数可以接受参数。"
        "函数也可以返回结果。"
    )

    sentences = split_sentences(text)

    assert sentences == [
        "Python函数可以封装逻辑。",
        "函数可以接受参数。",
        "函数也可以返回结果。",
    ]

def test_split_sentences_should_support_english():
    text = (
        "Python is useful. "
        "Functions reduce repetition. "
        "They can return values."
    )

    sentences = split_sentences(text)

    assert sentences == [
        "Python is useful.",
        "Functions reduce repetition.",
        "They can return values.",
    ]

def test_split_sentences_empty_text():
    assert split_sentences("") == []

def test_build_sentence_chunks_should_keep_sentences_complete():
    text = (
        "Python函数可以封装逻辑。"
        "函数可以接受参数。"
        "函数也可以返回结果。"
    )

    chunks = build_sentence_chunks(
        text,
        chunk_size=20,
    )

    assert chunks == [
        "Python函数可以封装逻辑。",
        "函数可以接受参数。函数也可以返回结果。",
    ]

def test_build_sentence_chunks_should_combine_short_sentences():
    text = (
        "第一句。"
        "第二句。"
        "第三句。"
    )

    chunks = build_sentence_chunks(
        text,
        chunk_size=20,
    )

    assert chunks == [
        "第一句。第二句。第三句。",
    ]

def test_build_sentence_chunks_should_split_long_sentence():
    text = "abcdefghij。"

    chunks = build_sentence_chunks(
        text,
        chunk_size=5,
    )

    assert chunks == [
        "abcde",
        "fghij",
        "。",
    ]

def test_build_sentence_chunks_empty_text():
    chunks = build_sentence_chunks(
        "",
        chunk_size=10,
    )

    assert chunks == []

def test_add_overlap():
    chunks = [
        "abcdef",
        "ghijkl",
    ]

    result = add_overlap(
        chunks,
        overlap=2,
    )

    assert result == [
        "abcdef",
        "efghijkl",
    ]

def test_add_overlap_zero_should_keep_chunks():
    chunks = [
        "abc",
        "def",
    ]

    result = add_overlap(
        chunks,
        overlap=0,
    )

    assert result == [
        "abc",
        "def",
    ]

def test_chunk_document_should_prefer_sentence_boundaries():
    document = KnowledgeDocument(
        title="test",
        content=(
            "第一句。"
            "第二句。"
            "第三句。"
        ),
        source="test.txt",
    )

    chunks = chunk_document(
        document,
        chunk_size=8,
        overlap=0,
    )

    assert chunks[0].content == (
        "第一句。第二句。"
    )

    assert chunks[1].content == (
        "第三句。"
    )