import pytest
from knowledge.service import KnowledgeService


def test_should_register_document_when_adding_file(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text(
        "Python函数用于封装重复使用的逻辑。",
        encoding="utf-8",
    )

    service = KnowledgeService()

    document, chunks = service.add_document(file_path)

    assert service.list_documents() == [document]
    assert service.get_document(document.id) == document
    assert len(chunks) > 0


def test_should_delete_document_and_chunks(tmp_path):
    file_path = tmp_path / "test.txt"
    file_path.write_text(
        "Python函数用于封装重复使用的逻辑。",
        encoding="utf-8",
    )

    service = KnowledgeService()

    document, _ = service.add_document(file_path)

    deleted = service.delete_document(document.id)

    assert deleted == document
    assert service.get_document(document.id) is None
    assert service.store.get_by_document_id(document.id) == []


def test_should_return_none_when_deleting_missing_document():
    service = KnowledgeService()

    deleted = service.delete_document("missing-document")

    assert deleted is None


class FakeEmbeddingProvider:
    def embed(self, text):
        return [1.0, 0.0, 0.0]


class FailingEmbeddingProvider:
    def embed(self, text):
        raise RuntimeError("embedding failed")


def test_should_delete_document_chunks_and_vectors_without_affecting_other_document(
    tmp_path,
):
    file_path_1 = tmp_path / "python.txt"
    file_path_1.write_text(
        "Python函数用于封装重复使用的逻辑。",
        encoding="utf-8",
    )

    file_path_2 = tmp_path / "loop.txt"
    file_path_2.write_text(
        "Python循环用于重复执行代码。",
        encoding="utf-8",
    )

    service = KnowledgeService(
        embedding_provider=FakeEmbeddingProvider(),
    )

    document_1, _ = service.add_document(file_path_1)
    document_2, _ = service.add_document(file_path_2)

    assert len(service.list_documents()) == 2
    assert len(service.store.get_by_document_id(document_1.id)) > 0
    assert len(service.store.get_by_document_id(document_2.id)) > 0
    assert len(service.vector_store.list_all()) == 2

    deleted = service.delete_document(document_1.id)

    assert deleted == document_1

    assert service.get_document(document_1.id) is None
    assert service.store.get_by_document_id(document_1.id) == []

    remaining_vectors = service.vector_store.list_all()

    assert all(item.chunk.document_id != document_1.id for item in remaining_vectors)

    assert service.get_document(document_2.id) == document_2
    assert len(service.store.get_by_document_id(document_2.id)) > 0

    assert all(item.chunk.document_id == document_2.id for item in remaining_vectors)


def test_should_update_document_without_changing_document_id(tmp_path):
    original_path = tmp_path / "original.txt"
    original_path.write_text(
        "Python函数用于封装重复使用的逻辑。",
        encoding="utf-8",
    )

    updated_path = tmp_path / "updated.txt"
    updated_path.write_text(
        "Python变量用于保存程序运行中的数据。",
        encoding="utf-8",
    )

    service = KnowledgeService(
        embedding_provider=FakeEmbeddingProvider(),
    )

    original_document, original_chunks = service.add_document(
        original_path,
        chunk_size=25,
    )

    original_chunk_ids = {chunk.id for chunk in original_chunks}

    result = service.update_document(
        original_document.id,
        updated_path,
        chunk_size=25,
    )

    updated_document, updated_chunks = result

    assert updated_document.id == original_document.id
    assert updated_document.content != original_document.content

    assert service.get_document(original_document.id) == updated_document

    current_chunks = service.store.get_by_document_id(original_document.id)

    assert current_chunks == updated_chunks

    current_chunk_ids = {chunk.id for chunk in current_chunks}

    assert original_chunk_ids.isdisjoint(current_chunk_ids)

    assert all("变量" in chunk.content for chunk in current_chunks)

    vectors = service.vector_store.list_all()

    assert all(item.chunk.document_id == original_document.id for item in vectors)

    assert all(item.chunk.id in current_chunk_ids for item in vectors)


def test_should_return_none_when_updating_missing_document(tmp_path):
    file_path = tmp_path / "updated.txt"
    file_path.write_text(
        "新的知识内容。",
        encoding="utf-8",
    )

    service = KnowledgeService()

    result = service.update_document(
        "missing-document",
        file_path,
    )

    assert result is None


def test_should_preserve_existing_knowledge_when_update_file_does_not_exist(
    tmp_path,
):
    original_path = tmp_path / "original.txt"
    original_path.write_text(
        "Python函数用于封装重复使用的逻辑。",
        encoding="utf-8",
    )

    service = KnowledgeService(
        embedding_provider=FakeEmbeddingProvider(),
    )

    original_document, original_chunks = service.add_document(
        original_path,
        chunk_size=25,
    )

    original_vectors = service.vector_store.list_all()

    missing_path = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError):
        service.update_document(
            original_document.id,
            missing_path,
            chunk_size=25,
        )

    assert service.get_document(original_document.id) == original_document

    assert service.store.get_by_document_id(original_document.id) == original_chunks

    assert service.vector_store.list_all() == original_vectors


def test_should_preserve_existing_knowledge_when_embedding_update_fails(
    tmp_path,
):
    original_path = tmp_path / "original.txt"
    original_path.write_text(
        "Python函数用于封装重复使用的逻辑。",
        encoding="utf-8",
    )

    updated_path = tmp_path / "updated.txt"
    updated_path.write_text(
        "Python变量用于保存程序运行中的数据。",
        encoding="utf-8",
    )

    service = KnowledgeService(
        embedding_provider=FakeEmbeddingProvider(),
    )

    original_document, original_chunks = service.add_document(
        original_path,
        chunk_size=25,
    )

    original_vectors = service.vector_store.list_all()

    service.embedding_provider = FailingEmbeddingProvider()

    with pytest.raises(RuntimeError, match="embedding failed"):
        service.update_document(
            original_document.id,
            updated_path,
            chunk_size=25,
        )

    assert service.get_document(original_document.id) == original_document

    assert service.store.get_by_document_id(original_document.id) == original_chunks

    assert service.vector_store.list_all() == original_vectors
