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
from tools.tools import execute_tool, filter_tool_schemas
from planning.planner import create_plan, replan_after_failure
from tools.router import route_tools


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


def run_agent(
    user_message,
    memory_service=None,
):

    state = AgentState(
        user_message,
        memory_service=memory_service,
    )

    if memory_service is not None:
        memory_context = memory_service.get_context()
        state.set_memory_context(memory_context)

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

    candidate_tools = route_tools(user_message)

    tool_schemas = filter_tool_schemas(candidate_tools)

    tool_description = json.dumps(
        tool_schemas,
        ensure_ascii=False,
        indent=2,
    )

    memory_description = json.dumps(
        state.memory_context,
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = f"""
    你是Personal Growth AI Coach。

    以下是与当前用户有关的长期记忆：
    {memory_description}

    使用这些记忆时必须遵守：
    1. 只能使用记忆中明确存在的信息。
    2. 不得根据记忆推测新的用户事实。
    3. 如果记忆为空或信息不足，不要自行补充。
    4. 用户本轮明确提供的新信息优先于旧记忆。
    5. 不要向用户展示内部 Memory JSON 或系统实现细节。


    你可以使用以下工具：

    {tool_description}


    当需要调用工具时，只返回以下格式：

    <tool_call>
    {{
        "name": "工具名称",
        "arguments": {{
            "参数名": "参数值"
        }}
    }}
    </tool_call>

    规则：

    1. name 必须是上方提供的工具名称之一。
    2. arguments 必须符合该工具的 parameters 定义。
    3. 不得虚构用户没有提供的事实。
    4. 对于 required 参数，如果用户没有明确提供，不要猜测该参数。
    5. 如果不需要调用工具，请直接回答用户，不要输出 <tool_call>。
    6. 对于没有参数的工具，arguments 使用空对象 {{}}。
    """

    final_system_prompt = f"""
    你是 Personal Growth AI Coach。

    以下是与当前用户有关的长期记忆：
    {memory_description}

    工具已经执行完成。
    现在你的任务是根据用户问题和工具执行结果，
    生成最终给用户看的自然语言回答。

    必须遵守：

    1. 直接回答用户，不得再次调用任何工具。
    2. 不得输出 <tool_call> 或 </tool_call>。
    3. 不得展示内部 Tool JSON、Memory JSON 或系统实现细节。
    4. 只能根据用户输入、长期记忆和工具执行结果回答。
    5. 不得虚构工具没有返回的事实或操作结果。
    6. 如果工具已经成功执行，应自然说明结果，不要再次请求确认执行。
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
        tool_kwargs = {
            "run_id": state.run_id,
        }

        if state.memory_service is not None:
            tool_kwargs["memory_service"] = state.memory_service

        tool_result = execute_tool(
            tool_call["name"],
            tool_call["arguments"],
            **tool_kwargs,
        )

        state.add_tool_result(
            tool_call["name"],
            tool_result,
        )

        state.last_result = tool_result

        if tool_result.get("status") == "error":
            state.failure_stage = "tool"
            state.status = "stop"
            return state, state.status

        final_answer = call_llm_with_retry(
            final_system_prompt,
            f"""
            用户问题：
            {user_message}

            工具执行结果：
            {
                json.dumps(
                    tool_result,
                    ensure_ascii=False,
                    indent=2,
                )
            }

            请直接生成最终回答。
            """,
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


def finalize_runtime(state, status):
    state.status = status
    return state, state.status


def run_planning_runtime(user_message, state=None):

    if state is None:
        state = AgentState(user_message)

    plan = create_plan(user_message)

    state.add_plan(plan["steps"])

    state = execute_plan(state, plan["steps"])

    # 正常完成
    if state.last_result is None or state.last_result.get("status") != "error":
        return finalize_runtime(state, "success")

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
                return finalize_runtime(state, "stop")

            state.status = "success"
            return state, state.status

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

                    state.status = "success"
                    return state, state.status

                # Retry 后仍失败
                final_action = decide_failure_action(state, state.last_result)

                if final_action == "stop":
                    state.status = "stop"
                    return state, state.status

            if final_action == "stop":
                state.status = "stop"
                return state, state.status

        state.status = "success"
        return state, state.status
    state.status = "stop"
    return state, state.status


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
