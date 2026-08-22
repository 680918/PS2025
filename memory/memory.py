import os


MEMORY_PATH = "memory"


MEMORY_FILES = {
    "skill": "skill_map.md",
    "learning": "learning_log.md",
    "profile": "user_profile.md",
    "project": "project_state.md",
    "experience": "experience_memory.md",
}


def get_memory_context(memory_type):

    file_name = MEMORY_FILES.get(memory_type)

    if file_name is None:
        return {"status": "error", "message": f"Unknown memory type: {memory_type}"}

    file_path = os.path.join(MEMORY_PATH, file_name)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        return {"status": "success", "memory_type": memory_type, "content": content}

    except FileNotFoundError:
        return {"status": "error", "message": f"Memory file not found: {file_name}"}


def update_memory(file_name, content):

    file_path = os.path.join(MEMORY_PATH, file_name)

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(content)

    return {"status": "success", "file": file_name}


def get_user_profile_structured():

    return {
        "status": "success",
        "tool_name": "get_user_profile",
        "data": {
            "age": 58,
            "technical_level": "技术入门阶段",
            "goal": "一年内掌握AI Agent应用搭建能力",
            "daily_learning_time": "1小时",
            "preferred_learning_time": "下午3点左右",
            "learning_preferences": ["原理", "实践", "结构", "案例", "系统化"],
            "strength": [
                "喜欢理解底层逻辑",
                "重视系统结构",
                "善于从现实案例抽象规律",
                "愿意通过项目实践学习",
            ],
            "weakness": [
                "Python实践不足",
                "缺少调试经验",
            ],
        },
    }


def get_skill_map_structured():

    return {
        "status": "success",
        "tool_name": "get_skill_map",
        "data": {
            "AI Agent": {
                "level": 90,
                "evidence": [
                    "理解Controller、LLM、Tool、Memory关系",
                    "理解Tool Calling流程",
                ],
            },
            "Python": {"level": 15, "weakness": ["不熟悉Python开发", "缺少调试经验"]},
        },
    }
