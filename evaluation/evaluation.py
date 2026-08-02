def evaluate_learning(
    topic,
    user_feedback,
    practice_result
):

    result = {

        "topic": topic,

        "understanding": 0,

        "strengths": [],

        "weaknesses": [],

        "next_step": []

    }


    if "理解" in user_feedback:

        result["understanding"] = 70


    if "不会代码" in user_feedback:

        result["weaknesses"].append(
            "Python实践不足"
        )


        result["next_step"].append(
            "增加代码练习"
        )


    return result