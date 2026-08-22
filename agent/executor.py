from tools.tools import execute_tool


def execute_plan(state, plan):

    for step in plan:
        state = execute_step(state, step)

        if state.last_result and state.last_result.get("status") == "error":
            return state

    return state


def execute_step(state, step):

    tool_name = step["tool"]

    arguments = resolve_arguments(state, step)

    result = execute_tool(tool_name, arguments)

    result_key = step.get("save_as", tool_name)

    state.add_tool_result(result_key, result)

    state.last_result = result

    state.current_step = step["step"]

    return state


def resolve_arguments(state, step):

    arguments = {}

    for key in step.get("arguments_from_state", []):
        arguments[key] = state.get_tool_result(key)

    return arguments
