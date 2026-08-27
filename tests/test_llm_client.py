import pytest

import llm_client


pytestmark = pytest.mark.unit


def test_call_llm_requires_api_key(monkeypatch):

    monkeypatch.setattr(llm_client, "DEEPSEEK_API_KEY", None)

    result = llm_client.call_llm("system", "hello")

    assert result["status"] == "error"

    assert result["error_type"] == "missing_api_key"

    assert result["content"] is None


def test_call_llm_success(monkeypatch):

    monkeypatch.setattr(
        llm_client,
        "DEEPSEEK_API_KEY",
        "fake-test-key",
    )

    class FakeResponse:
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


def test_call_llm_api_error(monkeypatch):

    monkeypatch.setattr(
        llm_client,
        "DEEPSEEK_API_KEY",
        "fake-test-key",
    )

    class FakeResponse:
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
