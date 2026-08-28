import pytest

import llm_client


pytestmark = pytest.mark.unit


def test_call_llm_requires_api_key(monkeypatch):

    monkeypatch.setattr(llm_client, "DEEPSEEK_API_KEY", None)

    result = llm_client.call_llm("system", "hello")

    assert result["status"] == "error"

    assert result["error_type"] == "missing_api_key"

    assert result["content"] is None

    assert result["retryable"] is False

    assert result["replannable"] is False


def test_call_llm_success(monkeypatch):

    monkeypatch.setattr(
        llm_client,
        "DEEPSEEK_API_KEY",
        "fake-test-key",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):

            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "测试回答",
                        }
                    }
                ]
            }

    def fake_post(
        url,
        headers,
        json,
        timeout,
    ):

        return FakeResponse()

    monkeypatch.setattr(
        llm_client.requests,
        "post",
        fake_post,
    )

    result = llm_client.call_llm(
        "system prompt",
        "hello",
    )

    assert result["status"] == "success"

    assert result["content"] == "测试回答"

    assert result["status"] == "success"


def test_call_llm_api_error(monkeypatch):

    monkeypatch.setattr(
        llm_client,
        "DEEPSEEK_API_KEY",
        "fake-test-key",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):

            return {"error": {"message": "test api error"}}

    def fake_post(
        url,
        headers,
        json,
        timeout,
    ):

        return FakeResponse()

    monkeypatch.setattr(
        llm_client.requests,
        "post",
        fake_post,
    )

    result = llm_client.call_llm(
        "system prompt",
        "hello",
    )

    assert result["status"] == "error"

    assert result["error_type"] == "llm_api_error"

    assert "test api error" in result["message"]

    assert result["content"] is None

    assert result["retryable"] is False

    assert result["replannable"] is False


def test_call_llm_timeout(monkeypatch):

    monkeypatch.setattr(
        llm_client,
        "DEEPSEEK_API_KEY",
        "fake-test-key",
    )

    def fake_post(
        url,
        headers,
        json,
        timeout,
    ):

        raise llm_client.requests.exceptions.Timeout("request timed out")

    monkeypatch.setattr(
        llm_client.requests,
        "post",
        fake_post,
    )

    result = llm_client.call_llm(
        "system",
        "hello",
    )

    assert result["status"] == "error"

    assert result["error_type"] == "llm_timeout"

    assert result["content"] is None

    assert result["retryable"] is True

    assert result["replannable"] is False


def test_call_llm_connection_error(monkeypatch):

    monkeypatch.setattr(
        llm_client,
        "DEEPSEEK_API_KEY",
        "fake-test-key",
    )

    def fake_post(
        url,
        headers,
        json,
        timeout,
    ):

        raise llm_client.requests.exceptions.ConnectionError("connection failed")

    monkeypatch.setattr(
        llm_client.requests,
        "post",
        fake_post,
    )

    result = llm_client.call_llm(
        "system",
        "hello",
    )

    assert result["status"] == "error"

    assert result["error_type"] == "llm_connection_error"

    assert result["content"] is None

    assert result["retryable"] is True

    assert result["replannable"] is False


def test_call_llm_http_error(monkeypatch):

    monkeypatch.setattr(
        llm_client,
        "DEEPSEEK_API_KEY",
        "fake-test-key",
    )

    class FakeResponse:
        def raise_for_status(self):

            raise llm_client.requests.exceptions.HTTPError("500 Server Error")

    def fake_post(
        url,
        headers,
        json,
        timeout,
    ):

        return FakeResponse()

    monkeypatch.setattr(
        llm_client.requests,
        "post",
        fake_post,
    )

    result = llm_client.call_llm(
        "system",
        "hello",
    )

    assert result["status"] == "error"

    assert result["error_type"] == "llm_http_error"

    assert result["content"] is None

    assert result["retryable"] is False

    assert result["replannable"] is False


def test_call_llm_invalid_json(monkeypatch):

    monkeypatch.setattr(
        llm_client,
        "DEEPSEEK_API_KEY",
        "fake-test-key",
    )

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("invalid json")

    def fake_post(
        url,
        headers,
        json,
        timeout,
    ):

        return FakeResponse()

    monkeypatch.setattr(
        llm_client.requests,
        "post",
        fake_post,
    )

    result = llm_client.call_llm(
        "system",
        "hello",
    )

    assert result["status"] == "error"

    assert result["error_type"] == "llm_invalid_response"

    assert result["content"] is None

    assert result["retryable"] is False

    assert result["replannable"] is False
