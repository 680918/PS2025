learning_memory = {

    "last_learning": {
        "date": "2026-07-15",
        "topic": "Tool Calling",
        "understanding": 70,
        "difficulty": "tool,skill,memory的概念还不能清晰分辨",
        "next_step": "进一步理解tool,skill,memory的区别"
    }

}

# 新增：能力地图

skill_map = {

    "AI Agent": "⭐⭐⭐⭐",

    "Prompt设计": "⭐⭐⭐",

    "Memory设计": "⭐⭐⭐",

    "Planning": "⭐⭐⭐⭐",

    "Tool Calling": "⭐⭐⭐",

    "Python": "⭐"

}



def get_memory():

    return learning_memory



# 新增函数

def get_skills():

    return skill_map
