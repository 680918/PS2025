from coach.response_policy import apply_response_policy


def test_should_remove_internal_metadata_lines():
    content = (
        "正常回答\n"
        "document_id: doc-1\n"
        "chunk_id: chunk-1\n"
        "chunk_index: 2\n"
        "score: 0.92\n"
        "rank: 1"
    )

    result = apply_response_policy(content)

    assert "正常回答" in result
    assert "document_id" not in result
    assert "chunk_id" not in result
    assert "chunk_index" not in result
    assert "score: 0.92" not in result
    assert "rank: 1" not in result


def test_should_preserve_source():
    content = (
        "正常回答\n"
        "source: python.txt"
    )

    result = apply_response_policy(content)

    assert "source: python.txt" in result


def test_should_not_remove_normal_score_word():
    content = "你的考试 score 提高了。"

    result = apply_response_policy(content)

    assert result == content


def test_should_remove_quoted_metadata_field():
    content = (
        '正常回答\n'
        '"chunk_id": "chunk-123"\n'
        '"score": 0.88'
    )

    result = apply_response_policy(content)

    assert '"chunk_id"' not in result
    assert '"score"' not in result
    assert "正常回答" in result


def test_should_return_non_string_input_unchanged():
    content = {"content": "test"}

    result = apply_response_policy(content)

    assert result == content