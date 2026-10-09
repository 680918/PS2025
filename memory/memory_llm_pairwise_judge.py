import json

from llm_client import call_llm


_VALID_EFFECTS = {
    "positive",
    "neutral",
    "negative",
}


_PAIRWISE_SYSTEM_PROMPT = """
你是一名 Memory Contribution Pairwise Judge。

你的任务不是分别给两个回答打绝对分数。

你必须直接比较两个回答，判断加入 Memory 后，
回答质量是否发生了实质性变化。

你只能依据：
1. 用户问题
2. 评价标准
3. 无 Memory 回答
4. 有 Memory 回答

判断 Memory 对回答质量的影响。

effect 只能是以下三种之一：

positive:
加入 Memory 后，回答在正确性、相关性、完整性、
连续性或实际帮助程度上有明显提升。

neutral:
加入 Memory 后，没有产生实质性的回答质量变化。

negative:
加入 Memory 后，回答质量明显下降，产生错误、
误导、遗漏重要内容或不合理的个性化。

特别注意：

- 不要分别给两个回答独立打分。
- 必须直接比较两份回答。
- 轻微的措辞、风格或表达方式变化，
  如果没有实质性提高回答质量，应判断为 neutral。
- 单纯增加个性化措辞，不代表 positive。
- 单纯出现不同措辞，也不代表 negative。
- 重点判断 Memory 是否造成实质性的质量变化。

只能返回严格 JSON：

{
  "effect": "positive|neutral|negative",
  "reason": "简短的中文判断理由"
}

要求：

- reason 必须使用简体中文。
- reason 应解释两份回答之间的关键质量差异。
- 不要返回 Markdown。
- 不要返回 JSON 以外的任何文字。
""".strip()


def _build_pairwise_user_message(
    query,
    without_memory_answer,
    with_memory_answer,
    evaluation_criteria,
):
    criteria_text = "\n".join(f"- {criterion}" for criterion in evaluation_criteria)

    return (
        f"用户问题:\n{query}\n\n"
        f"评价标准:\n{criteria_text}\n\n"
        "无 Memory 回答:\n"
        f"{without_memory_answer}\n\n"
        "有 Memory 回答:\n"
        f"{with_memory_answer}"
    )


def judge_memory_contribution_pair(
    query,
    without_memory_answer,
    with_memory_answer,
    evaluation_criteria,
    llm_call=call_llm,
):
    if (
        not isinstance(
            evaluation_criteria,
            list,
        )
        or not evaluation_criteria
    ):
        raise ValueError("evaluation_criteria must be a non-empty list")

    user_message = _build_pairwise_user_message(
        query,
        without_memory_answer,
        with_memory_answer,
        evaluation_criteria,
    )

    response = llm_call(
        _PAIRWISE_SYSTEM_PROMPT,
        user_message,
    )

    if response.get("status") != "success":
        raise RuntimeError("Pairwise Judge LLM call failed")

    try:
        result = json.loads(response["content"])
    except (
        json.JSONDecodeError,
        KeyError,
        TypeError,
    ) as error:
        raise ValueError("Pairwise Judge returned invalid JSON") from error

    effect = result.get("effect")
    reason = result.get("reason")

    if effect not in _VALID_EFFECTS:
        raise ValueError(f"invalid effect: {effect}")

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")

    return {
        "effect": effect,
        "reason": reason.strip(),
    }
