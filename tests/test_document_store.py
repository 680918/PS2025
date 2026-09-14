from knowledge.document_store import DocumentStore
from knowledge.models import KnowledgeDocument


def make_document(title="Python基础"):
    return KnowledgeDocument(
        title=title,
        content="Python函数用于封装可重复使用的逻辑。",
        source="data/knowledge/python_basics.txt",
    )


def test_should_add_document():
    store = DocumentStore()
    document = make_document()

    result = store.add(document)

    assert result == document
    assert store.list_all() == [document]


def test_should_get_document_by_id():
    store = DocumentStore()
    document = make_document()

    store.add(document)

    result = store.get_by_id(document.id)

    assert result == document


def test_should_return_none_when_document_not_found():
    store = DocumentStore()

    result = store.get_by_id("missing-document")

    assert result is None


def test_should_delete_document_by_id():
    store = DocumentStore()
    document = make_document()

    store.add(document)

    result = store.delete_by_id(document.id)

    assert result == document
    assert store.list_all() == []


def test_should_return_none_when_deleting_missing_document():
    store = DocumentStore()

    result = store.delete_by_id("missing-document")

    assert result is None


def test_should_replace_existing_document():
    store = DocumentStore()

    original = make_document()

    store.add(original)

    updated = KnowledgeDocument(
        id=original.id,
        title="Python进阶",
        content="更新后的内容",
        source="data/knowledge/python_advanced.txt",
        created_at=original.created_at,
    )

    result = store.replace(updated)

    assert result == updated
    assert store.get_by_id(original.id) == updated
    assert store.list_all() == [updated]


def test_should_return_none_when_replacing_missing_document():
    store = DocumentStore()

    document = make_document()

    result = store.replace(document)

    assert result is None
