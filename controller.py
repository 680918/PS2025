from llm_client import call_llm



def run_agent(user_input):


    system_prompt = """
你是Personal Growth AI Coach。

你的目标：
帮助用户系统学习AI Agent。

回答要求：
先分析用户需求，
再给出学习建议。
"""


    answer = call_llm(
        system_prompt,
        user_input
    )


    return answer