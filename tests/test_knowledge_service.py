from knowledge.service import KnowledgeService


def test_add_document_should_load_chunk_and_store(tmp_path):
    file_path = tmp_path / "python.txt"

    file_path.write_text(
        "Python函数可以封装重复逻辑。",
        encoding="utf-8",
    )

    service = KnowledgeService()

    document, chunks = service.add_document(
        file_path,
        chunk_size=100,
    )

    assert document.title == "python"
    assert len(chunks) == 1
    assert len(service.list_chunks()) == 1
    assert chunks[0].document_id == document.id


def test_search_should_return_matching_chunks(tmp_path):
    file_path = tmp_path / "python.txt"

    file_path.write_text(
        "Python 函数可以封装重复逻辑。",
        encoding="utf-8",
    )

    service = KnowledgeService()

    service.add_document(file_path)

    results = service.search(
        "Python 函数",
    )

    assert len(results) == 1
    assert "Python" in results[0].chunk.content
    assert results[0].score > 0


def test_search_should_respect_top_k(tmp_path):
    file_path = tmp_path / "python.txt"

    file_path.write_text(
        "PythonPythonPythonPython",
        encoding="utf-8",
    )

    service = KnowledgeService()

    service.add_document(
        file_path,
        chunk_size=6,
    )

    results = service.search(
        "Python",
        top_k=2,
    )

    assert len(results) == 2


def test_empty_knowledge_base_should_return_no_results():
    service = KnowledgeService()

    results = service.search(
        "Python",
    )

    assert results == []

def test_add_document_should_support_overlap(tmp_path):
    file_path = tmp_path / "test.txt"

    file_path.write_text(
        "abcdefghij",
        encoding="utf-8",
    )

    service = KnowledgeService()

    document, chunks = service.add_document(
        file_path,
        chunk_size=6,
        overlap=2,
    )

    assert len(chunks) == 2
    assert chunks[0].content == "abcdef"
    assert chunks[1].content == "efghij"
    assert chunks[0].document_id == document.id
    assert chunks[1].document_id == document.id