import json

from llm_client import call_llm

from memory.memory_answer_quality import (
    validate_answer_quality_score,
)


_JUDGE_SYSTEM_PROMPT = """
You are an answer quality evaluator.

Evaluate the answer only against the supplied
query and evaluation criteria.

Return strict JSON only:

{
  "score": 0.0,
  "reason": "brief explanation"
}

The score must be a number between 0 and 1.

0 means the answer fails the criteria.
1 means the answer fully satisfies the criteria.

Do not include markdown or any text outside
the JSON object.
""".strip()


def _build_judge_user_message(
    query,
    answer,
    evaluation_criteria,
):
    criteria_text = "\n".join(f"- {criterion}" for criterion in evaluation_criteria)

    return (
        f"Query:\n{query}\n\nAnswer:\n{answer}\n\nEvaluation criteria:\n{criteria_text}"
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
