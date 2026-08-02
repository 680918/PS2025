from llm_client import call_llm
from tools.tools import execute_tool
from tools.parser import parse_tool_call



def run_agent(user_message):


    system_prompt = """
    你是Personal Growth AI Coach

    如果需要用户能力信息，
    返回tool_call:
    get_memory_context

    """


    response = call_llm(
        system_prompt,
        user_message
    )


    tool_call = parse_tool_call(
        response
    )


    if tool_call:


        tool_result = execute_tool(
            tool_call["name"],
            tool_call["arguments"]
        )


        final_answer = call_llm(
            system_prompt,
            str(tool_result)
        )


        return final_answer


    else:

        return response