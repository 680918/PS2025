from llm_client import call_llm
from tools.tools import execute_tool
from tools.parser import parse_tool_call



def run_agent(user_message):


    system_prompt = """
你是Personal Growth AI Coach。

如果需要用户能力信息，
返回：

<tool_call>
get_memory_context
</tool_call>

"""


    response = call_llm(
        system_prompt,
        user_message
    )


    tool_call = parse_tool_call(
        response["content"]
    )


    if tool_call:


        tool_result = execute_tool(
            tool_call["name"],
            tool_call["arguments"]
        )


        final_answer = call_llm(
            system_prompt,
            f"""
用户问题：

{user_message}


工具返回：

{tool_result}


请根据工具信息回答用户。
"""
        )


        return final_answer["content"]


    else:

        return response["content"]