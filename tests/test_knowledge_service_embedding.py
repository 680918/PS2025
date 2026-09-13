from pathlib import Path

from knowledge.service import KnowledgeService


class FakeEmbeddingProvider:
    def embed(self, text):
        if "函数" in text or "封装" in text:
            return [1.0, 0.0]

        if "变量" in text or "数据" in text:
            return [0.0, 1.0]

        return [0.5, 0.5]


def test_knowledge_service_should_use_embedding_search(
    tmp_path,
):
    file_path = Path(tmp_path) / "python.txt"

    file_path.write_text(
        ("Python函数可以封装重复逻辑。\nPython变量用于保存程序运行中的数据。"),
        encoding="utf-8",
    )

    service = KnowledgeService(
        embedding_provider=(FakeEmbeddingProvider()),
    )

    service.add_document(
        file_path,
        chunk_size=15,
    )

    results = service.search(
        "如何封装重复逻辑？",
        top_k=1,
    )

    assert len(results) == 1

    assert "函数" in (results[0].chunk.content)


def test_knowledge_service_should_fallback_to_lexical_search(
    tmp_path,
):
    file_path = Path(tmp_path) / "python.txt"

    file_path.write_text(
        "Python函数可以封装重复逻辑。",
        encoding="utf-8",
    )

    service = KnowledgeService()

    service.add_document(
        file_path,
    )

    results = service.search(
        "Python函数",
        top_k=1,
    )

    assert len(results) == 1
