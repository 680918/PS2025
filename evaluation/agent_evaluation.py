from dataclasses import asdict, dataclass


def evaluate_agent_response(
    user_message,
    response,
    memory_context=None,
    knowledge_context=None,
):
    goal_alignment = evaluate_goal_alignment(
        user_message,
        response,
    )

    actionability = evaluate_actionability(
        response,
    )

    memory_usage = evaluate_memory_usage(
        response=response,
        memory_context=memory_context,
    )

    response_policy = evaluate_response_policy(response)

    knowledge_usage = evaluate_knowledge_usage(
        response=response,
        knowledge_context=knowledge_context,
    )

    overall_score = (
        goal_alignment
        + actionability
        + memory_usage
        + knowledge_usage
        + response_policy
    ) / 5

    passed = overall_score >= 0.5

    findings = generate_findings(
        goal_alignment,
        actionability,
        memory_usage,
        knowledge_usage,
        response_policy,
    )

    improvement_suggestions = generate_improvement_suggestions(
        goal_alignment,
        actionability,
        memory_usage,
        knowledge_usage,
        response_policy,
    )

    result = AgentEvaluationResult(
        goal_alignment=goal_alignment,
        actionability=actionability,
        memory_usage=memory_usage,
        knowledge_usage=knowledge_usage,
        response_policy=response_policy,
        overall_score=overall_score,
        passed=passed,
        findings=findings,
        improvement_suggestions=improvement_suggestions,
    )

    return result.to_dict()


def evaluate_actionability(response):
    action_keywords = [
        "完成",
        "练习",
        "阅读",
        "记录",
        "运行",
        "创建",
        "修改",
        "测试",
        "复习",
        "开始",
    ]

    step_keywords = [
        "第一步",
        "第二步",
        "先",
        "然后",
        "接着",
    ]

    has_action_keyword = any(keyword in response for keyword in action_keywords)

    has_step_structure = any(keyword in response for keyword in step_keywords)

    if has_action_keyword or has_step_structure:
        return 1.0

    return 0.0


def evaluate_goal_alignment(
    user_message,
    response,
):
    goal_terms = [
        [
            "AI Agent",
            "智能体",
        ],
        [
            "Tool Calling",
            "工具调用",
        ],
        [
            "Memory",
            "记忆",
        ],
        [
            "Planning",
            "规划",
        ],
        [
            "学习路线",
            "学习计划",
        ],
        [
            "下一步",
            "步骤",
        ],
    ]

    matched = False

    for group in goal_terms:
        user_has_term = any(term in user_message for term in group)

        response_has_term = any(term in response for term in group)

        if user_has_term and response_has_term:
            matched = True
            break

    return 1.0 if matched else 0.0


def generate_findings(
    goal_alignment,
    actionability,
    memory_usage,
    knowledge_usage,
    response_policy,
):
    findings = []

    if goal_alignment == 0.0:
        findings.append("回答没有覆盖用户目标")

    if actionability == 0.0:
        findings.append("回答缺少明确下一步行动")

    if memory_usage == 0.0:
        findings.append("回答没有有效使用相关记忆信息")

    if knowledge_usage == 0.0:
        findings.append("回答没有有效使用相关知识库内容")

    if response_policy == 0.0:
        findings.append("回答暴露了不应展示的内部系统信息")

    return findings


def generate_improvement_suggestions(
    goal_alignment,
    actionability,
    memory_usage,
    knowledge_usage,
    response_policy,
):
    suggestions = []

    if goal_alignment == 0.0:
        suggestions.append("下一次回答应更直接围绕用户的核心目标展开")

    if actionability == 0.0:
        suggestions.append("下一次回答应提供明确、可执行的下一步行动")

    if memory_usage == 0.0:
        suggestions.append("下一次回答应优先使用与当前问题相关的记忆信息")

    if knowledge_usage == 0.0:
        suggestions.append("下一次回答应优先使用与当前问题相关的知识库内容")

    if response_policy == 0.0:
        suggestions.append("下一次回答应移除内部元数据、工具调用标记和系统状态信息")

    return suggestions


@dataclass
class AgentEvaluationResult:
    goal_alignment: float
    actionability: float
    memory_usage: float
    knowledge_usage: float
    response_policy: float
    overall_score: float
    passed: bool
    findings: list
    improvement_suggestions: list

    def to_dict(self):
        return asdict(self)


def evaluate_memory_usage(
    response,
    memory_context=None,
):
    if not memory_context:
        return 1.0

    memory_values = []

    for value in memory_context.values():
        if isinstance(value, str) and value.strip():
            memory_values.append(value.strip())

    if not memory_values:
        return 1.0

    for value in memory_values:
        if value in response:
            return 1.0

    return 0.0


def evaluate_knowledge_usage(
    response,
    knowledge_context=None,
):
    if not knowledge_context:
        return 1.0

    for item in knowledge_context:
        if not isinstance(item, dict):
            continue

        source = item.get("source")

        if isinstance(source, str) and source.strip() and source.strip() in response:
            return 1.0

        content = item.get("content")

        if isinstance(content, str) and content.strip() and content.strip() in response:
            return 1.0

    return 0.0


def evaluate_response_policy(response):
    forbidden_markers = [
        "document_id",
        "chunk_id",
        "chunk_index",
        "score=",
        "rank=",
        "<tool_call>",
        "</tool_call>",
        "Memory JSON",
        "State JSON",
    ]

    for marker in forbidden_markers:
        if marker in response:
            return 0.0

    return 1.0
