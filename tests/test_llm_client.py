import pytest

import llm_client


pytestmark = pytest.mark.unit


def test_call_llm_requires_api_key(monkeypatch):

    monkeypatch.setattr(llm_client, "DEEPSEEK_API_KEY", None)

    with pytest.raises(ValueError, match="Missing DEEPSEEK_API_KEY"):
        llm_client.call_llm("system", "hello")
