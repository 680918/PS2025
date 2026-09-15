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
from coach.final_response_adapter import build_final_response_input
from coach.error_presenter import (
    present_final_response_error,
    present_runtime_error,
)
from coach.response_policy import apply_response_policy
from knowledge.scope_resolver import resolve_document_scope

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
    knowledge_service=None,
    document_ids=None,
):

    state = AgentState(
        user_message,
        memory_service=memory_service,
    )

    if memory_service is not None:
        memory_context = memory_service.get_context()
        state.set_memory_context(memory_context)

    if knowledge_service is not None:
        if document_ids is None:
            available_documents = knowledge_service.list_documents()

            document_ids = resolve_document_scope(
                user_message,
                available_documents,
                top_n=3,
            )
        results = knowledge_service.search(
            user_message,
            top_k=3,
            document_ids=document_ids,
        )

        knowledge_context = [
            {
                "chunk_id": result.chunk.id,
                "document_id": result.chunk.document_id,
                "content": result.chunk.content,
                "source": result.chunk.source,
                "chunk_index": result.chunk.chunk_index,
                "score": result.score,
                "rank": rank,
            }
            for rank, result in enumerate(
                results,
                start=1,
            )
        ]

        state.set_knowledge_context(knowledge_context)

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

    knowledge_description = json.dumps(
        state.knowledge_context,
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = f"""
    你是Personal Growth AI Coach。

    以下是与当前用户有关的长期记忆：
    {memory_description}

    以下是从知识库中检索到的相关资料：
    {knowledge_description}

    使用知识库资料时必须遵守：
    1. 如果资料与用户当前问题直接相关，应优先依据这些资料回答。
    2. 不得仅因为系统提供了检索资料，就假定这些资料足以回答用户问题。
    3. 必须判断检索到的资料是否真正支持当前问题。
    4. 不得把资料中没有明确出现的内容伪装成知识库事实。
    5. 如果知识库为空，或者检索到的资料不足以支持用户当前问题，
    必须先明确告诉用户：“当前知识库没有相关内容”。
    6. 如果随后使用模型自身的通用知识继续回答，
    必须明确说明：“以下基于通用知识回答”。
    7. 不得让用户误以为模型自身的通用知识来自知识库。
    8. 不得向用户展示内部 Knowledge JSON、Chunk 结构或检索实现细节。
    9. 如果回答实际使用了知识库资料，可以使用资料中的 source 字段，
    以自然语言向用户说明知识来源。
    10. 不得向用户展示 document_id、chunk_id、chunk_index、score、rank
    等内部检索元数据。

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

    以下是从知识库中检索到的相关资料：
    {knowledge_description}

    使用知识库资料时必须遵守：
    1. 如果资料与用户当前问题直接相关，应优先依据这些资料回答。
    2. 不得仅因为系统提供了检索资料，就假定这些资料足以回答用户问题。
    3. 必须判断检索到的资料是否真正支持当前问题。
    4. 不得把资料中没有明确出现的内容伪装成知识库事实。
    5. 如果知识库为空，或者检索到的资料不足以支持用户当前问题，
    必须先明确告诉用户：“当前知识库没有相关内容”。
    6. 如果随后使用用户输入、长期记忆、工具结果或模型自身通用知识继续回答，
    必须清楚区分这些信息与知识库内容。
    7. 如果使用模型自身的通用知识回答，
    必须明确说明：“以下基于通用知识回答”。
    8. 不得让用户误以为非知识库信息来自知识库。
    9. 不得向用户展示内部 Knowledge JSON、Chunk 结构或检索实现细节。
    10. 如果回答实际使用了知识库资料，可以使用资料中的 source 字段，
    以自然语言向用户说明知识来源。
    11. 不得向用户展示 document_id、chunk_id、chunk_index、score、rank
    等内部检索元数据。

    工具已经执行完成。


    现在你的任务是根据用户问题和工具执行结果，
    生成最终给用户看的自然语言回答。

    必须遵守：

    1. 直接回答用户，不得再次调用任何工具。
    2. 不得输出 <tool_call> 或 </tool_call>。
    3. 不得展示内部 Tool JSON、Memory JSON 或系统实现细节。
    4. 只能根据用户输入、长期记忆、知识库资料和工具执行结果回答。
    5. 不得虚构工具没有返回的事实或操作结果。
    6. 如果工具已经成功执行，应自然说明结果，不要再次请求确认执行。
    7. 如果工具结果中包含 next_learning_action、next_learning_topic 或 next_learning_reason，
       必须优先依据这些字段生成下一步学习建议。
    8. 如果 next_learning_topic 不为空，不得自行推荐与其不同的下一学习主题。
    9. 不得用“你想继续学什么”“你想选哪个方向”等开放式问题替代已经存在的 Planning Decision。
    10. 可以补充简短解释，但不得覆盖、改写或否定 Planner 已经给出的下一步决策。
    11. 不得把高理解度、高分或单次测验结果表述为“完全掌握”。
        应使用“当前证据显示掌握度较高”“当前表现较稳定”等谨慎措辞。
    12. 除非系统已经实际创建了日程、提醒或计划，
        不得使用“已经为你安排”“明天几点开始”“到时开始学习”等
        暗示系统已经执行安排的确定性措辞。
    13. 必须区分事实、评估和建议。
        工具返回的数据是事实或系统评估；
        Planner 返回的是下一步建议；
        不得把建议描述成已经发生的事实。
    14. 可以解释 next_learning_reason，
        但不得补充工具结果和长期记忆中没有证据支持的用户状态、
        学习经历或能力结论。
    15. 如果工具执行结果中存在 coach_response，
        必须优先使用 coach_response 生成最终回答。
    16. coach_response.facts 表示已记录事实。
        coach_response.assessment 包含：
        - status：学习趋势状态
        - confidence：评估置信度
        - current_understanding：当前理解程度
        coach_response.recommendation 包含：
        - action：Planner 决定的学习动作
        - next_topic：Planner 决定的下一学习主题
        - reason：Planner 给出该建议的原因。
    17. 必须以 coach_response.recommendation.action、
        coach_response.recommendation.next_topic 和
        coach_response.recommendation.reason 为准，
        不得重新规划、改写或替换其中的核心决策。
    18. 可以把 facts、assessment、recommendation 转换成自然语言，
        但不得改变它们的语义层级，也不得补充没有证据支持的新结论。
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

        final_response_input = build_final_response_input(tool_result)

        final_answer = call_llm_with_retry(
            final_system_prompt,
            f"""
            用户问题：
            {user_message}

            最终回答输入：
            {
                json.dumps(
                    final_response_input,
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
        user_error = present_runtime_error(state)

        retry_text = "你可以稍后再试一次。" if user_error.retry_suggested else ""

        return f"{user_error.title}：{user_error.message}{retry_text}"

    if state.last_result:
        content = state.last_result.get("content", "")
        return apply_response_policy(content)

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
            return finalize_runtime(state, "stop")

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
                    return finalize_runtime(state, "stop")

            return finalize_runtime(state, "success")

        return finalize_runtime(state, "stop")

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
                    return finalize_runtime(state, "stop")

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
                        return finalize_runtime(state, "stop")

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
        user_error = present_runtime_error(state)

        retry_text = "你可以稍后再试一次。" if user_error.retry_suggested else ""

        return f"{user_error.title}：{user_error.message}{retry_text}"

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
        user_error = present_final_response_error()

        retry_text = "你可以稍后再试一次。" if user_error.retry_suggested else ""

        return f"{user_error.title}：{user_error.message}{retry_text}"

    return apply_response_policy(response["content"])
