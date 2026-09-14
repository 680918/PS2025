from knowledge.service import KnowledgeService


class FakeEmbeddingProvider:
    def embed(self, text):
        if "函数" in text:
            return [1.0, 0.0]

        if "循环" in text:
            return [0.0, 1.0]

        return [0.5, 0.5]


def create_file(
    tmp_path,
    name,
    content,
):
    file_path = tmp_path / name
    file_path.write_text(
        content,
        encoding="utf-8",
    )
    return file_path


def test_should_search_only_selected_document_with_lexical_retrieval(
    tmp_path,
):
    function_path = create_file(
        tmp_path,
        "function.txt",
        "Python函数用于封装重复使用的逻辑。",
    )

    loop_path = create_file(
        tmp_path,
        "loop.txt",
        "Python循环用于重复执行代码。",
    )

    service = KnowledgeService()

    function_document, _ = service.add_document(function_path)
    loop_document, _ = service.add_document(loop_path)

    results = service.search(
        "Python函数",
        document_ids=[loop_document.id],
    )

    assert all(result.chunk.document_id == loop_document.id for result in results)

    assert all(result.chunk.document_id != function_document.id for result in results)


def test_should_search_only_selected_document_with_vector_retrieval(
    tmp_path,
):
    function_path = create_file(
        tmp_path,
        "function.txt",
        "Python函数用于封装重复使用的逻辑。",
    )

    loop_path = create_file(
        tmp_path,
        "loop.txt",
        "Python循环用于重复执行代码。",
    )

    service = KnowledgeService(
        embedding_provider=FakeEmbeddingProvider(),
    )

    function_document, _ = service.add_document(function_path)
    loop_document, _ = service.add_document(loop_path)

    results = service.search(
        "Python函数",
        document_ids=[loop_document.id],
    )

    assert all(result.chunk.document_id == loop_document.id for result in results)

    assert all(result.chunk.document_id != function_document.id for result in results)


def test_should_search_all_documents_when_scope_is_none(
    tmp_path,
):
    function_path = create_file(
        tmp_path,
        "function.txt",
        "Python函数用于封装重复使用的逻辑。",
    )

    loop_path = create_file(
        tmp_path,
        "loop.txt",
        "Python循环用于重复执行代码。",
    )

    service = KnowledgeService()

    function_document, _ = service.add_document(function_path)
    loop_document, _ = service.add_document(loop_path)

    results = service.search(
        "Python",
        document_ids=None,
    )

    result_document_ids = {result.chunk.document_id for result in results}

    assert function_document.id in result_document_ids
    assert loop_document.id in result_document_ids


def test_should_return_empty_results_when_scope_is_empty(
    tmp_path,
):
    function_path = create_file(
        tmp_path,
        "function.txt",
        "Python函数用于封装重复使用的逻辑。",
    )

    service = KnowledgeService()

    service.add_document(function_path)

    results = service.search(
        "Python函数",
        document_ids=[],
    )

    assert results == []
