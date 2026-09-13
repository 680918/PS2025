import pytest

from knowledge.loader import load_document


def test_load_txt_document(tmp_path):
    file_path = tmp_path / "notes.txt"
    file_path.write_text(
        "这是学习资料。",
        encoding="utf-8",
    )

    document = load_document(file_path)

    assert document.title == "notes"
    assert document.content == "这是学习资料。"
    assert document.source == str(file_path)


def test_load_markdown_document(tmp_path):
    file_path = tmp_path / "system.md"
    file_path.write_text(
        "# 系统思维\n增强回路会强化变化。",
        encoding="utf-8",
    )

    document = load_document(file_path)

    assert document.title == "system"
    assert "增强回路" in document.content


def test_load_document_should_reject_unsupported_file(tmp_path):
    file_path = tmp_path / "book.pdf"
    file_path.write_text(
        "fake pdf",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_document(file_path)


def test_load_document_should_raise_when_file_missing(tmp_path):
    file_path = tmp_path / "missing.txt"

    with pytest.raises(FileNotFoundError):
        load_document(file_path)