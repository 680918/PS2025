import json


def parse_tool_call(response_text):

    if "<tool_call>" not in response_text:
        return None

    start = response_text.find("<tool_call>")
    end = response_text.find("</tool_call>")

    if end == -1:
        return None

    content = response_text[start + len("<tool_call>") : end].strip()

    if not content:
        return None

    # New JSON format
    if content.startswith("{"):
        try:
            tool_call = json.loads(content)
        except json.JSONDecodeError:
            return None

        if not isinstance(tool_call, dict):
            return None

        tool_name = tool_call.get("name")

        if not isinstance(tool_name, str) or not tool_name.strip():
            return None

        arguments = tool_call.get("arguments", {})

        if not isinstance(arguments, dict):
            return None

        return {
            "name": tool_name.strip(),
            "arguments": arguments,
        }

    # Legacy format
    return {
        "name": content,
        "arguments": {},
    }
