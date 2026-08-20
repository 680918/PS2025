def create_plan(user_message):

    # if "学习路线" in user_message or "提升AI Agent" in user_message:
    if (
        "学习路线" in user_message
        or "提升AI Agent" in user_message
        or "学习计划" in user_message
        or "学习规划" in user_message
        or "学习什么？" in user_message
    ):
        return {

            "goal":
            "提升AI Agent能力",

            "steps":
            [

                {
                    "step":1,

                    "tool": "get_user_profile",
                    "save_as": "user_profile",
                    "reason": "了解用户背景、兴趣和长期目标"
                },


                {
                    "step":2,

                    "tool": "get_skill_map",
                    "save_as": "skill_map",
                    "reason": "测试Retry失败后的Replan,了解当前能力水平和学习历史"
                },


                {
                    "step":3,
                    "tool": "create_learning_plan",                 
                    "reason": "根据用户状态生成学习计划",               

                    "arguments_from_state":
                    [
                    "user_profile",
                    "skill_map"
                    ]
                }

            ]
        }


    return {

        "goal":
        user_message,

        "steps":[]

    }

def replan_after_failure(
        user_message,
        failed_key,
        state
    ):

    if failed_key == "skill_map":

        return {

            "goal": "提升AI Agent能力",
            "steps": [
                
                {
                "step": 1,
                "tool": "create_learning_plan",
                "reason": "skill_map获取失败, 基于已有user_profile生成基础学习计划",
                "arguments_from_state": 
                    [
                    "user_profile"
                    ]
                 }         
            ]
        }

    return {
        "goal": user_message,
        "steps": []
    }