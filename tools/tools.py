from memory.memory import get_memory, get_skills



def get_learning_history():

    """
    Tool:

    查询学习历史
    """

    history = get_memory()

    return history

# 新增Tool

def get_skill_map():

    """
    Tool:

    查询能力地图
    """

    skills = get_skills()

    return skills