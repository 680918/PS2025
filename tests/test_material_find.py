import pytest

from coach.materials import MaterialRepository
from tests.test_web_book_section import pdf_with_blank_middle


def test_literal_original_search_is_owned_bounded_and_keeps_selection(tmp_path):
    repo = MaterialRepository(tmp_path / "materials.db")
    query = "知识的实际运用"
    own = repo.add(
        "one",
        "notes.txt",
        ("开头" * 500 + query + "正文" * 500).encode(),
        title="阅读笔记",
    )
    foreign = repo.add("two", "private.txt", (query + "其他用户的独有内容").encode())
    repo.select("one", own)
    before = repo.database_path.read_bytes()
    hits = repo.find_chunks("one", query)
    assert hits and all(hit["material_id"] == own for hit in hits)
    assert all(hit["chunk_index"] > 1 for hit in hits)
    assert all("content" not in hit and "raw" not in hit for hit in hits)
    assert all(query in hit["search_match"]["excerpt"]["text"] for hit in hits)
    assert all(
        len(hit["search_match"]["excerpt"]["text"]) <= len(query) + 140 for hit in hits
    )
    assert repo.find_chunks("one", query, material_id=foreign) == []
    assert (
        repo.find_chunks("one", "阅读笔记") == []
    )  # Original text, not a title match.
    assert repo.database_path.read_bytes() == before
    restarted = MaterialRepository(repo.database_path)
    assert restarted.selected("one")["material_id"] == own
    assert restarted.find_chunks("one", query) == hits


def test_pagination_has_no_missing_chunks_or_unbounded_original_text(tmp_path):
    repo = MaterialRepository(tmp_path / "materials.db")
    book = repo.add("one", "book.txt", (("命中" + "甲" * 798) * 25).encode())
    first = repo.find_chunks("one", "命中", material_id=book)
    second = repo.find_chunks("one", "命中", material_id=book, page=2)
    assert len(first) == 21 and len(second) == 5
    assert [hit["chunk_index"] for hit in first[:20] + second] == list(range(1, 26))
    assert first[20] == second[0]
    assert repo.find_chunks("one", "命中", page=3) == []


def test_filtering_and_order_are_stable_for_multiple_materials(tmp_path):
    repo = MaterialRepository(tmp_path / "materials.db")
    one = repo.add("one", "one.txt", "关键词，第一个资料。".encode())
    two = repo.add("one", "two.txt", "关键词，第二个资料。".encode())
    assert {hit["material_id"] for hit in repo.find_chunks("one", "关键词")} == {
        one,
        two,
    }
    assert [
        hit["material_id"] for hit in repo.find_chunks("one", "关键词", material_id=two)
    ] == [two]
    assert repo.find_chunks("one", "关键词") == repo.find_chunks("one", "关键词")


@pytest.mark.parametrize(
    "query, expected",
    [
        ("ABC", True),
        ("abc", True),
        ("%_'", True),
        ("i", False),
        ("ss", False),
        ("' OR 1=1 --", False),
    ],
)
def test_queries_are_literal_and_unicode_offsets_are_not_casefolded(
    tmp_path, query, expected
):
    repo = MaterialRepository(tmp_path / "materials.db")
    repo.add("one", "literal.txt", "ABC %_' İ ß".encode())
    hits = repo.find_chunks("one", query)
    assert bool(hits) == expected


def test_pdf_results_keep_actual_page_including_blank_pages(tmp_path):
    repo = MaterialRepository(tmp_path / "materials.db")
    book = repo.add("one", "book.pdf", pdf_with_blank_middle())
    found = repo.find_chunks("one", "SPACED", material_id=book)
    assert [hit["locator"] for hit in found] == [
        "PDF 第 1 页 · 片段 1",
        "PDF 第 3 页 · 片段 2",
    ]


@pytest.mark.parametrize("query", [None, 42, "a" * 121, "a\nb", "a\0b", "a\ud800b"])
def test_invalid_query_cannot_read_materials(tmp_path, query):
    repo = MaterialRepository(tmp_path / "materials.db")
    with pytest.raises(ValueError):
        repo.find_chunks("one", query)


@pytest.mark.parametrize("page", [True, "1", 0, -1, 10001, 1.5])
def test_invalid_page_rejected(tmp_path, page):
    repo = MaterialRepository(tmp_path / "materials.db")
    with pytest.raises(ValueError):
        repo.find_chunks("one", "word", page=page)


def test_empty_search_is_empty_and_malformed_filter_is_rejected(tmp_path):
    repo = MaterialRepository(tmp_path / "materials.db")
    repo.add("one", "book.txt", b"readable")
    assert repo.find_chunks("one", "  ") == []
    for value in ("../../outside", [], "f" * 33):
        with pytest.raises(ValueError):
            repo.find_chunks("one", "word", material_id=value)
