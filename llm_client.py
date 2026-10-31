import requests

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    LLM_TIMEOUT,
    LLM_TEMPERATURE,
)

from core.errors import make_error


def call_llm(system_prompt, user_message):

    if not DEEPSEEK_API_KEY:
        return make_error(
            error_type="missing_api_key",
            message="Missing DEEPSEEK_API_KEY",
            retryable=False,
            replannable=False,
        )

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

    try:
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=LLM_TIMEOUT,
        )

        response.raise_for_status()

    except requests.exceptions.Timeout as e:
        return make_error(
            error_type="llm_timeout",
            message=str(e),
            retryable=True,
            replannable=False,
        )

    except requests.exceptions.ConnectionError as e:
        return make_error(
            error_type="llm_connection_error",
            message=str(e),
            retryable=True,
            replannable=False,
        )

    except requests.exceptions.HTTPError as e:
        return make_error(
            error_type="llm_http_error",
            message=str(e),
            retryable=False,
            replannable=False,
        )

    except requests.exceptions.RequestException as e:
        # Keep an unexpected transport problem separate from a model reply.  The
        # caller intentionally turns this into a short, safe user-facing notice.
        return make_error(
            error_type="llm_request_error",
            message=str(e),
            retryable=True,
            replannable=False,
        )

    try:
        result = response.json()

    except ValueError as e:
        return make_error(
            error_type="llm_invalid_response",
            message=str(e),
            retryable=False,
            replannable=False,
        )

    try:
        return {
            "status": "success",
            "content": result["choices"][0]["message"]["content"],
        }
    except (IndexError, KeyError, TypeError):
        # Do not include a provider response body in errors: it can be large,
        # unhelpful, or contain text the user did not send to the Coach.
        return make_error(
            error_type="llm_invalid_response",
            message="Invalid LLM response shape",
            retryable=False,
            replannable=False,
        )
