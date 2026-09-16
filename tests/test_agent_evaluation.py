from evaluation.agent_evaluation import (
    AgentEvaluationResult,
    evaluate_agent_response,
)


def test_agent_evaluation_should_return_structured_result():
    result = evaluate_agent_response(
        user_message="我今天应该学习什么？",
        response=(
            "今天继续练习 Agent Tool Calling。"
            "先复习 Tool 和 Skill 的区别，"
            "然后完成一个实际工具调用练习。"
        ),
    )

    assert "goal_alignment" in result
    assert "actionability" in result
    assert "overall_score" in result
    assert "passed" in result


def test_agent_evaluation_should_mark_actionable_response():
    result = evaluate_agent_response(
        user_message="我今天应该学习什么？",
        response=("今天先复习 Tool 和 Skill 的区别，然后完成一个实际工具调用练习。"),
    )

    assert result["actionability"] == 1.0


def test_agent_evaluation_should_mark_non_actionable_response():
    result = evaluate_agent_response(
        user_message="我今天应该学习什么？",
        response="AI Agent 是一个很重要的学习方向。",
    )

    assert result["actionability"] == 0.0


def test_agent_evaluation_should_mark_goal_aligned_response():
    result = evaluate_agent_response(
        user_message=("我想一年内学会搭建AI智能体，现在应该怎么学习？"),
        response=(
            "根据你一年掌握AI Agent搭建能力的目标，"
            "当前应该先加强Tool Calling实践，"
            "然后逐步学习Evaluation和Pipeline。"
        ),
    )

    assert result["goal_alignment"] == 1.0


def test_agent_evaluation_should_mark_goal_misaligned_response():
    result = evaluate_agent_response(
        user_message=("我想一年内学会搭建AI智能体，现在应该怎么学习？"),
        response=("人工智能的发展历史包括机器学习、深度学习和大模型。"),
    )

    assert result["goal_alignment"] == 0.0


def test_agent_evaluation_should_return_findings():
    result = evaluate_agent_response(
        user_message=("我想一年内学会搭建AI智能体，现在应该怎么学习？"),
        response=("人工智能的发展历史包括机器学习、深度学习和大模型。"),
    )

    assert "findings" in result

    assert "回答没有覆盖用户目标" in result["findings"]


def test_agent_evaluation_should_not_report_problem_for_good_response():
    result = evaluate_agent_response(
        user_message=("我想一年内学会搭建AI智能体，现在应该怎么学习？"),
        response=(
            "根据你一年掌握AI Agent搭建能力的目标，"
            "当前先练习Tool Calling，"
            "然后学习Memory和Evaluation。"
        ),
    )

    assert result["findings"] == []


def test_agent_evaluation_should_generate_improvement_suggestions():
    result = evaluate_agent_response(
        user_message=("我想一年内学会搭建AI智能体，现在应该怎么学习？"),
        response=("人工智能的发展历史包括机器学习、深度学习和大模型。"),
    )

    assert "improvement_suggestions" in result

    assert len(result["improvement_suggestions"]) > 0


def test_good_response_should_have_no_improvement_suggestions():
    result = evaluate_agent_response(
        user_message=("我想一年内学会搭建AI智能体，现在应该怎么学习？"),
        response=(
            "根据你一年掌握AI Agent搭建能力的目标，"
            "当前先练习Tool Calling，"
            "然后学习Memory和Evaluation。"
        ),
    )

    assert result["improvement_suggestions"] == []


def test_agent_evaluation_result_should_have_stable_structure():
    result = AgentEvaluationResult(
        goal_alignment=1.0,
        actionability=1.0,
        memory_usage=1.0,
        knowledge_usage=1.0,
        response_policy=1.0,
        overall_score=1.0,
        passed=True,
        findings=[],
        improvement_suggestions=[],
    )

    assert result.goal_alignment == 1.0
    assert result.actionability == 1.0
    assert result.overall_score == 1.0
    assert result.passed is True
    assert result.findings == []
    assert result.improvement_suggestions == []


def test_agent_evaluation_result_should_convert_to_dict():
    result = AgentEvaluationResult(
        goal_alignment=1.0,
        actionability=0.0,
        memory_usage=1.0,
        knowledge_usage=1.0,
        response_policy=1.0,
        overall_score=0.5,
        passed=True,
        findings=["回答缺少明确下一步行动"],
        improvement_suggestions=["下一次回答应提供明确、可执行的下一步行动"],
    )

    result_dict = result.to_dict()

    assert result_dict["goal_alignment"] == 1.0
    assert result_dict["actionability"] == 0.0
    assert result_dict["overall_score"] == 0.5
    assert result_dict["passed"] is True


def test_evaluate_agent_response_should_return_dict_from_result_contract():
    result = evaluate_agent_response(
        user_message="我想学习AI智能体",
        response="先学习AI Agent基础，然后完成一个练习。",
    )

    assert isinstance(result, dict)

    assert set(result.keys()) == {
        "goal_alignment",
        "actionability",
        "memory_usage",
        "knowledge_usage",
        "response_policy",
        "overall_score",
        "passed",
        "findings",
        "improvement_suggestions",
    }


def test_agent_evaluation_result_should_include_memory_usage():
    result = AgentEvaluationResult(
        goal_alignment=1.0,
        actionability=1.0,
        memory_usage=1.0,
        knowledge_usage=1.0,
        response_policy=1.0,
        overall_score=1.0,
        passed=True,
        findings=[],
        improvement_suggestions=[],
    )

    assert result.memory_usage == 1.0


def test_agent_evaluation_should_mark_memory_as_used():
    result = evaluate_agent_response(
        user_message="我下一步应该学什么？",
        response=("根据你一年内学会搭建AI智能体的目标，下一步继续加强Python实践。"),
        memory_context={
            "learning_goal": "一年内学会搭建AI智能体",
            "python_level": "较弱",
        },
    )

    assert result["memory_usage"] == 1.0


def test_agent_evaluation_should_mark_memory_as_not_used():
    result = evaluate_agent_response(
        user_message="我下一步应该学什么？",
        response=("你可以学习一些人工智能相关知识。"),
        memory_context={
            "learning_goal": "一年内学会搭建AI智能体",
            "python_level": "较弱",
        },
    )

    assert result["memory_usage"] == 0.0


def test_agent_evaluation_should_report_unused_memory():
    result = evaluate_agent_response(
        user_message="我下一步应该学什么？",
        response="你可以学习一些人工智能相关知识。",
        memory_context={
            "learning_goal": "一年内学会搭建AI智能体",
            "python_level": "较弱",
        },
    )

    assert "回答没有有效使用相关记忆信息" in result["findings"]

    assert (
        "下一次回答应优先使用与当前问题相关的记忆信息"
        in result["improvement_suggestions"]
    )


def test_agent_evaluation_result_should_include_knowledge_usage():
    result = AgentEvaluationResult(
        goal_alignment=1.0,
        actionability=1.0,
        memory_usage=1.0,
        knowledge_usage=1.0,
        response_policy=1.0,
        overall_score=1.0,
        passed=True,
        findings=[],
        improvement_suggestions=[],
    )

    assert result.knowledge_usage == 1.0


def test_agent_evaluation_should_mark_knowledge_as_used():
    result = evaluate_agent_response(
        user_message="什么是系统思维？",
        response=(
            "系统思维强调理解变量之间的关系、"
            "反馈回路以及系统整体行为。"
            "来源：systems.txt"
        ),
        knowledge_context=[
            {
                "content": ("系统思维关注变量之间的关系、反馈回路和整体系统行为。"),
                "source": "systems.txt",
            }
        ],
    )

    assert result["knowledge_usage"] == 1.0


def test_agent_evaluation_should_mark_knowledge_as_not_used():
    result = evaluate_agent_response(
        user_message="什么是系统思维？",
        response="这是一个很重要的思考方法。",
        knowledge_context=[
            {
                "content": ("系统思维关注变量之间的关系、反馈回路和整体系统行为。"),
                "source": "systems.txt",
            }
        ],
    )

    assert result["knowledge_usage"] == 0.0


def test_agent_evaluation_should_report_unused_knowledge():
    result = evaluate_agent_response(
        user_message="什么是系统思维？",
        response="这是一个很重要的思考方法。",
        knowledge_context=[
            {
                "content": ("系统思维关注变量之间的关系、反馈回路和整体系统行为。"),
                "source": "systems.txt",
            }
        ],
    )

    assert "回答没有有效使用相关知识库内容" in result["findings"]

    assert (
        "下一次回答应优先使用与当前问题相关的知识库内容"
        in result["improvement_suggestions"]
    )


def test_agent_evaluation_should_mark_response_policy_as_compliant():
    result = evaluate_agent_response(
        user_message="请解释系统思维",
        response=("系统思维强调变量之间的关系、反馈回路和整体行为。"),
    )

    assert result["response_policy"] == 1.0

    assert set(result.keys()) == {
        "goal_alignment",
        "actionability",
        "memory_usage",
        "knowledge_usage",
        "response_policy",
        "overall_score",
        "passed",
        "findings",
        "improvement_suggestions",
    }


def test_agent_evaluation_should_report_response_policy_violation():
    result = evaluate_agent_response(
        user_message="请解释系统思维",
        response=("参考内容：document_id=doc-system, chunk_id=chunk-1, score=0.92"),
    )

    assert "回答暴露了不应展示的内部系统信息" in result["findings"]

    assert (
        "下一次回答应移除内部元数据、工具调用标记和系统状态信息"
        in result["improvement_suggestions"]
    )
