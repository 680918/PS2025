import logging
from tools.tools import execute_tool


logger = logging.getLogger(__name__)


def execute_plan(state, plan):

    logger.info(
        "Plan start: run_id=%s steps=%s",
        state.run_id,
        len(plan),
    )

    for step in plan:
        state = execute_step(state, step)

        if state.last_result and state.last_result.get("status") == "error":
            logger.error(
                "Plan stopped: run_id=%s step=%s error_type=%s",
                state.run_id,
                step["step"],
                state.last_result.get("error_type"),
            )
            return state

    logger.info(
        "Plan completed: run_id=%s steps=%s",
        state.run_id,
        len(plan),
    )

    return state


def execute_step(state, step):

    tool_name = step["tool"]

    logger.info(
        "Step start: run_id=%s step=%s tool_name=%s",
        state.run_id,
        step["step"],
        tool_name,
    )

    arguments = resolve_arguments(state, step)

    result = execute_tool(tool_name, arguments)

    if result.get("status") == "error":
        logger.error(
            "Step failed: run_id=%s step=%s tool_name=%s error_type=%s",
            state.run_id,
            step["step"],
            tool_name,
            result.get("error_type"),
        )
    else:
        logger.info(
            "Step success: run_id=%s step=%s tool_name=%s",
            state.run_id,
            step["step"],
            tool_name,
        )

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
