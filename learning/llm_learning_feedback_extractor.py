import json

from llm_client import call_llm


class LLMLearningFeedbackExtractor:
    def __init__(self, llm_call=None):
        self.llm_call = llm_call or call_llm

    def extract(self, user_message):
        system_prompt = """
你是学习反馈提取器。

你的任务是从用户本轮消息中识别明确表达的学习反馈。

只返回 JSON。

如果用户明确提供了完整学习反馈，格式必须是：

{
    "feedback": {
        "understanding_score": 0,
        "difficulty": "当前难点",
        "next_step": "下一步"
    }
}

如果用户没有明确提供完整学习反馈，格式必须是：

{
    "feedback": null
}

要求：
1. 只能提取用户本轮明确表达的信息。
2. 不得自行推测理解程度、难点或下一步。
3. understanding_score 必须是用户明确表达的 0 到 100 的整数。
4. 只有 understanding_score、difficulty、next_step 三项都明确存在时，
   才返回 feedback 对象。
5. 如果任意一项缺失，必须返回 {"feedback": null}。
6. 普通提问、讨论、求解释、求示例，不属于学习反馈。
7. 不要返回额外说明。
"""

        response = self.llm_call(
            system_prompt,
            user_message,
        )

        if response.get("status") == "error":
            raise RuntimeError("LLM learning feedback extraction failed")

        content = response.get("content")

        try:
            data = json.loads(content)
        except (TypeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "LLM learning feedback response is invalid JSON"
            ) from error

        feedback = data.get("feedback")

        if not isinstance(feedback, dict):
            return None

        understanding_score = feedback.get("understanding_score")
        difficulty = feedback.get("difficulty")
        next_step = feedback.get("next_step")

        if (
            not isinstance(understanding_score, int)
            or isinstance(understanding_score, bool)
            or not 0 <= understanding_score <= 100
        ):
            return None

        if not isinstance(difficulty, str) or not difficulty.strip():
            return None

        if not isinstance(next_step, str) or not next_step.strip():
            return None

        return {
            "understanding_score": understanding_score,
            "difficulty": difficulty.strip(),
            "next_step": next_step.strip(),
        }
