AGENT_EVALUATION_CASES = [
    {
        "case_id": "goal_alignment_001",
        "focus_metric": "goal_alignment",
        "user_message": "我想继续学习 Tool Calling。",
        "response": (
            "下一步继续学习 Tool Calling，重点练习工具调用参数和返回结果处理。"
        ),
        "memory_context": {},
        "knowledge_context": [],
    },
    {
        "case_id": "actionability_001",
        "focus_metric": "actionability",
        "user_message": "我下一步应该怎么练习？",
        "response": (
            "第一步运行现有 agent.py，"
            "然后修改一个 Tool 参数，"
            "最后重新运行测试并记录结果。"
        ),
        "memory_context": {},
        "knowledge_context": [],
    },
    {
        "case_id": "memory_usage_001",
        "focus_metric": "memory_usage",
        "user_message": "我下一步应该学习什么？",
        "response": (
            "根据你一年内学会搭建AI智能体的目标，下一步继续练习 Tool Calling。"
        ),
        "memory_context": {
            "learning_goal": "一年内学会搭建AI智能体",
        },
        "knowledge_context": [],
    },
    {
        "case_id": "knowledge_usage_001",
        "focus_metric": "knowledge_usage",
        "user_message": "系统思维里增强回路是什么？",
        "response": ("根据 systems.txt，增强回路会放大系统中的变化趋势。"),
        "memory_context": {},
        "knowledge_context": [
            {
                "content": "增强回路会放大系统中的变化趋势。",
                "source": "systems.txt",
            }
        ],
    },
    {
        "case_id": "response_policy_001",
        "focus_metric": "response_policy",
        "user_message": "请给我下一步学习建议。",
        "response": ("下一步继续练习 Agent Tool Calling，并完成一次测试。"),
        "memory_context": {},
        "knowledge_context": [],
    },
]
