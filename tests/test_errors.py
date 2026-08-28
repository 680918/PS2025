from core.errors import make_error
import pytest


def test_make_error_contract():
    result = make_error(
        error_type="test_error",
        message="something failed",
        retryable=True,
        replannable=False,
    )

    assert result["status"] == "error"
    assert result["error_type"] == "test_error"
    assert result["message"] == "something failed"
    assert result["content"] is None
    assert result["retryable"] is True
    assert result["replannable"] is False


def test_make_error_defaults():
    result = make_error(
        error_type="test_error",
        message="failed",
    )

    assert result["retryable"] is False
    assert result["replannable"] is False
    assert result["content"] is None


def test_make_error_rejects_empty_error_type():

    with pytest.raises(ValueError):
        make_error(
            error_type="",
            message="failed",
        )


def test_make_error_rejects_empty_message():

    with pytest.raises(ValueError):
        make_error(
            error_type="test_error",
            message="",
        )
