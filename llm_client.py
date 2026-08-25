import requests

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_TIMEOUT,
    LLM_TEMPERATURE,
)


def call_llm(system_prompt, user_message):

    if not DEEPSEEK_API_KEY:
        raise ValueError(
            "Missing DEEPSEEK_API_KEY"   )

    api_key = DEEPSEEK_API_KEY

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": LLM_TEMPERATURE,
    }

    response = requests.post(url, headers=headers, json=data, timeout=LLM_TIMEOUT)

    result = response.json()

    if "choices" in result:
        # return result["choices"][0]["message"]["content"]
        return result["choices"][0]["message"]

    else:
        return f"LLM调用失败:{result}"
