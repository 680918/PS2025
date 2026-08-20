def evaluate_learning_plan(
    plan,
    skill_map
):

    if skill_map["Python"]["level"] < 20:

        return {

        "status":"success",

        "score":70,

        "passed":False,

        "feedback":
        "Python基础不足"

        }

    else:

        return {

        "status":"success",

        "score":90,

        "passed":True

        }

def evaluate_learning_plan(
    plan,
    user_profile,
    skill_map
):

    score = 100

    feedback=[]


    python_level = (
        skill_map["Python"]["level"]
    )


    if python_level < 20:

        feedback.append(
            "Python基础不足，需要增加基础阶段"
        )

        score -= 20


    passed = score >= 80


    return {

        "status":"success",

        "score":score,

        "passed":passed,

        "feedback":feedback

    }