from llm_client import call_llm


class LLMJourneyCompletionCommentary:
    def __init__(self, llm_call=None):
        self.llm_call = llm_call or call_llm

    def generate(self, summary):
        system_prompt = """
你是一名学习教练。

请根据给定的学习旅程总结，
生成一段简洁、客观的毕业评语。

要求：
1. 只能根据提供的数据进行总结。
2. 不要编造用户已经掌握的能力。
3. 可以描述学习趋势、理解度变化和学习证据。
4. 不要输出 JSON。
"""

        user_message = f"""
学习领域：
{summary["domain"]}

学习目标：
{summary["goal"]}

完成学习次数：
{summary["completed_sessions"]}

最初理解度：
{summary["first_understanding"]}

最终理解度：
{summary["latest_understanding"]}

理解度变化：
{summary["understanding_change"]}

学习趋势：
{summary["trend"]}

学习证据数量：
{summary["evidence_count"]}

已完成任务：
{summary["completed_tasks"]}

学习信号：
{summary["learning_signal"]}

证据质量：
{summary["quality_summary"]}
"""

        response = self.llm_call(
            system_prompt,
            user_message,
        )

        if response.get("status") == "error":
            raise RuntimeError("LLM journey completion commentary generation failed")

        content = response.get("content")

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("LLM journey completion commentary is empty")

        return content
