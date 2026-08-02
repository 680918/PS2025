import os
import requests
from dotenv import load_dotenv


load_dotenv()


def call_llm(system_prompt, user_message):

    api_key = os.getenv("DEEPSEEK_API_KEY")

    url = "https://api.deepseek.com/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


    data = {
        "model": "deepseek-v4-flash",
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_message
            }
        ],
        "temperature": 0.7
    }


    response = requests.post(
        url,
        headers=headers,
        json=data,
        timeout=30
    )


    result = response.json()


    if "choices" in result:

        # return result["choices"][0]["message"]["content"]
        return result["choices"][0]["message"]

    else:

        return f"LLM调用失败:{result}"