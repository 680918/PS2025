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
        return {
            "status": "error",
            "error_type": "missing_api_key",
            "message": "Missing DEEPSEEK_API_KEY",
            "content": None,
        }

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }

    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
        "temperature": LLM_TEMPERATURE,
    }

    response = requests.post(
        url,
        headers=headers,
        json=data,
        timeout=LLM_TIMEOUT,
    )

    result = response.json()

    if "choices" in result:
        return {
            "status": "success",
            "content": result["choices"][0]["message"]["content"],
        }

    return {
        "status": "error",
        "error_type": "llm_api_error",
        "message": str(result),
        "content": None,
    }
