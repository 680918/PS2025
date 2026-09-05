import json
import logging
import time

from agent.executor import execute_plan, execute_step
from agent.task_router import route_task
from agent.state import AgentState
from config import (
    LLM_MAX_RETRIES,
    LLM_RETRY_DELAY,
    LLM_MAX_RETRY_DELAY,
)
from core.logging_context import get_trace_logger
from llm_client import call_llm
from tools.parser import parse_tool_call
from tools.tools import execute_tool, load_tool_schemas
from planning.planner import create_plan, replan_after_failure


logger = logging.getLogger(__name__)


def log_recovery_decision(state, action, error_type):
    trace_logger = get_trace_logger(
        logger,
        run_id=state.run_id,
    )
    if action == "stop":
        trace_logger.error(
            "Recovery decision: action=%s error_type=%s",
            action,
            error_type,
        )
    else:
        trace_logger.warning(
            "Recovery decision: action=%s error_type=%s",
            action,
            error_type,
        )


def decide_failure_action(state, result):
    if result.get("status") != "error":
        return "continue"

    if result.get("retryable") is True and state.can_retry():
        log_recovery_decision(
            state,
            "retry",
            result.get("error_type"),
        )
        return "retry"

    replannable = result.get("replannable", True)

    if replannable is True and state.can_replan():
        log_recovery_decision(
            state,
            "replan",
            result.get("error_type"),
        )
        return "replan"

    log_recovery_decision(
        state,
        "stop",
        result.get("error_type"),
    )

    return "stop"


def get_current_step(plan, current_step):
    for step in plan:
        if step["step"] == current_step:
            return step

    return None


def get_remaining_steps(plan, current_step):
    remaining_steps = []

    for step in plan:
        if step["step"] > current_step:
            remaining_steps.append(step)

    return remaining_steps


def call_llm_with_retry(system_prompt, user_message, run_id=None):
    trace_logger = get_trace_logger(
        logger,
        run_id=run_id,
    )
    response = call_llm(system_prompt, user_message)

    retries = 0

    while (
        response.get("status") == "error"
        and response.get("retryable") is True
        and retries < LLM_MAX_RETRIES
    ):
        delay = min(
            LLM_RETRY_DELAY * (2**retries),
            LLM_MAX_RETRY_DELAY,
        )

        trace_logger.warning(
            "LLM retry: error_type=%s retry=%s delay=%s",
            response.get("error_type"),
            retries + 1,
            delay,
        )

        time.sleep(delay)

        retries += 1

        response = call_llm(system_prompt, user_message)

    if (
        response.get("status") == "error"
        and response.get("retryable") is True
        and retries >= LLM_MAX_RETRIES
    ):
        trace_logger.error(
            "LLM retry exhausted: error_type=%s retries=%s",
            response.get("error_type"),
            retries,
        )

    return response


def run_agent(user_message):

    state = AgentState(user_message)

    task_type = route_task(user_message)

    if task_type == "planning":
        return run_planning_agent(
            user_message,
            state=state,
        )

    return run_simple_agent(
        user_message,
        state=state,
    )


def run_simple_runtime(user_message, state=None):

    if state is None:
        state = AgentState(user_message)

    tool_schemas = load_tool_schemas()

    tool_description = json.dumps(
        tool_schemas,
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = f"""
    你是Personal Growth AI Coach。

    你可以使用以下工具：

    {tool_description}


    当你需要外部信息时，
    请返回：

    <tool_call>
    工具名称
    </tool_call>

    根据用户问题自主选择工具。
    """

    response = call_llm_with_retry(
        system_prompt,
        user_message,
        run_id=state.run_id,
    )

    if response.get("status") == "error":
        state.last_result = response
        state.failure_stage = "initial_llm"
        state.status = "stop"
        return state, state.status

    tool_call = parse_tool_call(response["content"])

    if tool_call:
        tool_result = execute_tool(
            tool_call["name"],
            tool_call["arguments"],
            run_id=state.run_id,
        )

        state.add_tool_result(tool_call["name"], tool_result)
        state.last_result = tool_result

        if tool_result.get("status") == "error":
            state.failure_stage = "tool"
            state.status = "stop"
            return state, state.status

        final_answer = call_llm_with_retry(
            system_prompt,
            f"""
                            用户问题：{user_message}
                            工具返回：{tool_result}
                            请根据工具信息回答用户。""",
            run_id=state.run_id,
        )

        state.last_result = final_answer

        if final_answer.get("status") == "error":
            state.failure_stage = "final_llm"
            state.status = "stop"
            return state, state.status

        state.status = "success"
        return state, state.status

    state.last_result = response
    state.status = "success"
    return state, state.status


def run_simple_agent(user_message, state=None):

    state, runtime_status = run_simple_runtime(
        user_message,
        state=state,
    )

    if runtime_status == "stop":
        message = "未知错误"

        if state.last_result:
            message = state.last_result.get(
                "message",
                "未知错误",
            )

        if state.failure_stage == "tool":
            return f"工具调用失败：{message}"

        return f"LLM调用失败：{message}"

    if state.last_result:
        return state.last_result.get("content", "")

    return ""


def get_failed_key(state):

    for key, result in state.tool_results.items():
        if result.get("status") == "error":
            return key

    return None


# pytest
def run_planning_workflow(user_message):

    state = AgentState(user_message)

    plan = create_plan(user_message)

    state.add_plan(plan["steps"])

    state = execute_plan(state, plan["steps"])

    return state


def run_planning_runtime(user_message, state=None):

    if state is None:
        state = AgentState(user_message)

    plan = create_plan(user_message)

    state.add_plan(plan["steps"])

    state = execute_plan(state, plan["steps"])

    # 正常完成
    if state.last_result is None or state.last_result.get("status") != "error":
        return state, "success"

    action = decide_failure_action(state, state.last_result)

    # =========================
    # Retry
    # =========================

    if action == "retry":
        failed_step = get_current_step(plan["steps"], state.current_step)

        if failed_step is None:
            return state, "stop"

        state.record_retry()

        state = execute_step(state, failed_step)

        # Retry成功 → Resume
        if state.last_result and state.last_result.get("status") == "success":
            remaining_steps = get_remaining_steps(plan["steps"], state.current_step)

            if remaining_steps:
                state = execute_plan(state, remaining_steps)

            if state.last_result and state.last_result.get("status") == "error":
                return state, "stop"

            return state, "success"

        # Retry仍失败 → 再判断
        next_action = decide_failure_action(state, state.last_result)

        if next_action == "replan":
            state.record_replan()

            failed_key = get_failed_key(state)

            new_plan = replan_after_failure(user_message, failed_key, state)

            state.add_plan(new_plan["steps"])

            state = execute_plan(state, new_plan["steps"])

            if state.last_result and state.last_result.get("status") == "error":
                final_action = decide_failure_action(state, state.last_result)

                if final_action == "stop":
                    return state, "stop"

            return state, "success"

        return state, "stop"

    # =========================
    # Direct Replan
    # =========================

    elif action == "replan":
        state.record_replan()

        failed_key = get_failed_key(state)

        new_plan = replan_after_failure(user_message, failed_key, state)

        state.add_plan(new_plan["steps"])

        state = execute_plan(state, new_plan["steps"])

        if state.last_result and state.last_result.get("status") == "error":
            final_action = decide_failure_action(state, state.last_result)

            # Plan V2 发生可重试错误
            if final_action == "retry":
                failed_step = get_current_step(new_plan["steps"], state.current_step)

                if failed_step is None:
                    return state, "stop"

                state.record_retry()

                state = execute_step(state, failed_step)

                # Retry 成功
                if state.last_result and state.last_result.get("status") == "success":
                    remaining_steps = get_remaining_steps(
                        new_plan["steps"], state.current_step
                    )

                    if remaining_steps:
                        state = execute_plan(state, remaining_steps)

                    if state.last_result and state.last_result.get("status") == "error":
                        return state, "stop"

                    return state, "success"

                # Retry 后仍失败
                final_action = decide_failure_action(state, state.last_result)

                if final_action == "stop":
                    return state, "stop"

                return state, "stop"

            if final_action == "stop":
                return state, "stop"

        return state, "success"

    return state, "stop"


def run_planning_agent(user_message, state=None):

    state, runtime_status = run_planning_runtime(user_message, state=state)

    state_data = state.get_state()

    if runtime_status == "stop":
        stop_prompt = f"""
你是 Personal Growth AI Coach。

当前任务执行失败。

用户问题：
{user_message}

Agent 已经进行了允许范围内的重试和重新规划，
但仍然无法可靠完成任务。

以下是当前内部状态：

{json.dumps(state_data, ensure_ascii=False, indent=2)}

请向用户生成一段简洁、诚实、可理解的失败说明。

要求：
1. 不展示内部 JSON、State、Tool 名称或系统实现细节。
2. 说明当前无法完成任务的原因。
3. 不得假装任务已经成功。
4. 不得继续编造缺失信息。
5. 如果合适，可以告诉用户下一步可以怎么做。
"""

        response = call_llm_with_retry(stop_prompt, user_message, run_id=state.run_id)

        if response.get("status") == "error":
            return f"LLM调用失败：{response.get('message', '未知错误')}"

        return response["content"]

    final_prompt = f"""
你是 Personal Growth AI Coach。

用户问题：
{user_message}

下面是 Agent 已经完成规划和工具执行后得到的内部状态数据：

{json.dumps(state_data, ensure_ascii=False, indent=2)}

请严格根据以上 State 中已有的信息回答用户。

规则：
1. 不得编造 State 中没有的用户事实。
2. 不得自行假设用户的学习时间、技术基础、学习资源、框架选择或项目方向。
3. 可以解释、整理和归纳 State 中已有的信息。
4. 如果某项信息缺失，就明确说“当前信息不足”，不要猜。
5. 不要向用户展示内部 State、Tool 调用过程、JSON 或系统实现细节。
6. 回答应具体、清晰、可执行，但所有建议必须能从 State 中找到依据。
"""

    response = call_llm_with_retry(final_prompt, user_message, run_id=state.run_id)

    if response.get("status") == "error":
        return f"LLM调用失败：{response.get('message', '未知错误')}"

    return response["content"]
