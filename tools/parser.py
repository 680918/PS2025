# tools/parser.py


def parse_tool_call(response_text):

    if "<tool_call>" not in response_text:

        return None


    start = response_text.find(
        "<tool_call>"
    )

    end = response_text.find(
        "</tool_call>"
    )

    if end == -1:
        return None


    tool_name = response_text[
        start + len("<tool_call>"):
        end
    ].strip()


    return {

        "name": tool_name,

        "arguments": {}

    }