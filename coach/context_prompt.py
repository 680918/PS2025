import json


def build_coach_context_prompt(coach_context):
    if coach_context is None:
        return ""

    prompt_context = {}

    user_name = coach_context.user_context.get("name")

    if user_name:
        prompt_context["user"] = {
            "name": user_name,
        }

    learning_context = {
        key: coach_context.learning_context[key]
        for key in (
            "domain",
            "goal",
            "status",
        )
        if coach_context.learning_context.get(key) is not None
    }

    if learning_context:
        prompt_context["learning"] = learning_context

    if not prompt_context:
        return ""

    return json.dumps(
        prompt_context,
        ensure_ascii=False,
        indent=2,
    )
