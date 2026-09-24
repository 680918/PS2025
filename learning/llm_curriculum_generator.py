import json

from llm_client import call_llm


class LLMCurriculumGenerator:
    def __init__(self, llm_call=None):
        self.llm_call = llm_call or call_llm

    def generate(self, domain, goal):
        system_prompt = """
你是课程规划助手。

请根据用户的学习领域和学习目标，
生成一份按学习顺序排列的课程主题列表。

只返回 JSON，格式必须是：

{
    "curriculum_topics": [
        "主题1",
        "主题2",
        "主题3"
    ]
}

不要返回额外说明。
"""

        user_message = f"""
学习领域：
{domain}

学习目标：
{goal}
"""

        response = self.llm_call(
            system_prompt,
            user_message,
        )

        if response.get("status") == "error":
            raise RuntimeError("LLM curriculum generation failed")

        content = response["content"]

        try:
            data = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError("LLM curriculum response is invalid JSON") from error

        if "curriculum_topics" not in data:
            raise RuntimeError("LLM curriculum response is missing curriculum_topics")

        return data["curriculum_topics"]
