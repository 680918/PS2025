SAFE_TOOL_FIELDS = {
    "get_user_profile": [
        "goal",
        "technical_level",
        "learning_preferences",
    ],
    "get_skill_map": None,
}


def _filter_tool_data(tool_name, data):
    allowed_fields = SAFE_TOOL_FIELDS.get(tool_name)

    if tool_name not in SAFE_TOOL_FIELDS:
        return None

    if allowed_fields is None:
        return data

    return {key: data[key] for key in allowed_fields if key in data}


def build_final_response_input(tool_result):
    if not tool_result:
        return {}

    if tool_result.get("status") == "error":
        return {
            "status": "error",
            "tool_name": tool_result.get("tool_name"),
            "error_type": tool_result.get("error_type"),
            "message": tool_result.get("message"),
        }

    data = tool_result.get("data", {})
    coach_response = data.get("coach_response")

    if coach_response is not None:
        return {
            "facts": coach_response.get("facts", []),
            "assessment": coach_response.get("assessment"),
            "recommendation": coach_response.get("recommendation"),
        }

    tool_name = tool_result.get("tool_name")
    safe_data = _filter_tool_data(tool_name, data)

    result = {
        "tool_name": tool_name,
        "status": tool_result.get("status"),
    }

    if safe_data is not None:
        result["data"] = safe_data

    return result
