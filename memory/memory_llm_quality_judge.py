import json

from llm_client import call_llm

from memory.memory_answer_quality import (
    validate_answer_quality_score,
)


_JUDGE_SYSTEM_PROMPT = """
你是一名回答质量评估器。

你只能根据提供的：
1. 用户问题
2. 待评估回答
3. 评价标准

来评估回答质量。

只能返回严格 JSON：

{
  "score": 0.0,
  "reason": "简短的中文评价理由"
}

要求：

- score 必须是 0 到 1 之间的数字。
- 0 表示回答完全没有满足评价标准。
- 1 表示回答完全满足评价标准。
- reason 必须使用简体中文。
- reason 应解释为什么得到这个分数。
- 不要返回 Markdown。
- 不要返回 JSON 以外的任何文字。
""".strip()


def _build_judge_user_message(
    query,
    answer,
    evaluation_criteria,
):
    criteria_text = "\n".join(f"- {criterion}" for criterion in evaluation_criteria)

    return (
        f"用户问题：\n{query}\n\n待评估回答：\n{answer}\n\n评价标准：\n{criteria_text}"
    )


def score_answer_with_llm(
    query,
    answer,
    evaluation_criteria,
    llm_call=call_llm,
):
    response = llm_call(
        _JUDGE_SYSTEM_PROMPT,
        _build_judge_user_message(
            query,
            answer,
            evaluation_criteria,
        ),
    )

    if response.get("status") != "success":
        error_type = response.get(
            "error_type",
            "unknown_llm_error",
        )

        raise RuntimeError(f"LLM judge failed: {error_type}")

    content = response.get(
        "content",
        "",
    )

    try:
        payload = json.loads(content)
    except (
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError("invalid judge response") from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError("invalid judge response")

    if "score" not in payload or "reason" not in payload:
        raise ValueError("invalid judge response")

    score = validate_answer_quality_score(payload["score"])

    reason = payload["reason"]

    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("invalid judge response")

    return {
        "score": score,
        "reason": reason.strip(),
    }
