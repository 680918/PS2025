from memory.memory import get_memory_context
import os
import json
from memory.memory import (get_user_profile_structured, get_skill_map_structured)

def get_memory(
    memory_type="skill",
    topic=None
):

    return get_memory_context(
        memory_type
    )

def create_learning_plan(
    user_profile,
    skill_map = None
):

    profile_data = user_profile["data"]
    daily_time = profile_data["daily_learning_time"]
    learning_preferences = profile_data["learning_preferences"]

    if skill_map is None:

        focus = "基础学习与实践"

        reason = (
            "当前缺少完整的能力地图，"
            "因此先根据用户画像和长期目标生成基础学习计划。"
        )

        learning_plan = {

            "month_1": {
                "focus": "Python基础实践",
                "topics": [
                    "函数",
                    "字典",
                    "模块",
                    "文件读写",
                    "异常处理"
                ],
                "milestone":
                "完成一个可运行的小型Python程序"
            },

            "month_2": {
                "focus": "Agent基础组件",
                "topics": [
                    "Controller",
                    "State",
                    "Tool",
                    "Registry"
                ],
                "milestone":
                "理解并运行一个最小Agent闭环"
            },

            "month_3": {
                "focus": "Agent小项目",
                "topics": [
                    "Planner",
                    "Executor",
                    "Memory",
                    "测试"
                ],
                "milestone":
                "完成一个基础Agent Demo"
            }
        }

        return {
            "status": "success",
            "tool_name": "create_learning_plan",
            "data": {
                "mode": "degraded",
                "focus": focus,
                "reason": reason,
                "learning_preferences":
                learning_preferences,
                "daily_learning_time":
                daily_time,
                "plan":
                learning_plan
            }
        }


    skill_data = skill_map["data"]
    python_level = skill_data["Python"]["level"]
    agent_level = skill_data["AI Agent"]["level"]
    
    if python_level < 30:
        focus = "加强Python实践"

        reason = (
            f"当前python能力为{python_level}分，"
            f"明显低于AI Agent架构理解的{agent_level}分，"
            "现阶段应优先把架构理解转化为代码实践能力。"
        )

        learning_plan = {
            "month_1": {
                "focus": "python实践基础",
                "topics": [
                    "函数",
                    "字典",
                    "模块",
                    "文件读写",
                    "异常处理",
                    "代码信息流向"
                ],
                "milestone":
                "完成一个包含多个函数和文件读写的小型python程序"
            },
            "month_2": {

                "focus": "python组件代码化",
                "topics": [
                    "Controller",
                    "State",
                    "Tool",
                    "Registry",
                    "Structured Input/Output"
                ],
                "milestone":
                "独立完成一个最小Agent执行闭环"
            },

            "month_3":{
                "focus": "Agent项目实践",
                "topics": [
                    "Planner",
                    "Executor",
                    "Memory",
                    "错误处理",
                    "测试"
                ],
                "milestone":
                "完成一个可以持续迭代的Agent Demo"
            }
        }
    else:
        focus = "加强AI Agent项目实践"

        reason = (
            f"当前python能力为{python_level}分，"
            "已经具备进一步进行Agent项目实践的基础。"
        )

        learning_plan = {
            "month_1": {
                "focus": "Agent核心模块独立实现",
                "topics": [
                    "Controller",
                    "State",
                    "Tool",
                    "Registry",
                    "Executor"
                ],
                "milestone":
                "独立完成一个最小Agent执行闭环"
            },

            "month_2": {
                "focus": "Agent能力扩展",
                "topics": [
                    "Planner",
                    "Memory",
                    "Structured Output",
                    "错误处理",
                    "Evaluation"
                ],
                "milestone":
                "完成具备规划、记忆和评估能力的Agent"
            },

            "month_3": {
                "focus": "完整Agent项目",
                "topics": [
                    "项目架构",
                    "模块集成",
                    "测试",
                    "日志",
                    "迭代优化"
                ],
                "milestone":
                "完成一个可持续迭代的Agent Demo"
            }
        }
    
    return {
        "status": "success",
        "tool_name": "create_learning_plan",
        "data":
        {
            "mode": "full",
            "focus": focus,
            "reason": reason,
            "learning_preferences": learning_preferences,
            "daily_learning_time": daily_time,
            "plan": learning_plan
        }
    }

def get_user_profile():
    return get_user_profile_structured()

def get_skill_map():

    return get_skill_map_structured()

 
TOOLS = {
    
    "get_memory_context":
    get_memory,

    "get_user_profile":
    get_user_profile,

    "get_skill_map":
    get_skill_map,

    "create_learning_plan":
    create_learning_plan
      
}

def execute_tool(
    tool_name,
    arguments=None
):

    tool = TOOLS.get(tool_name)

    if tool is None:

        return {
            "status": "error",
            "error_type": "unknown_tool",
            "message": f"Unknown tool: {tool_name}",
            "retryable": False
        }

    try:

        if arguments:
            return tool(**arguments)

        else:
            return tool()

    except FileNotFoundError as e:

        return {
            "status": "error",
            "error_type": "file_not_found",
            "message": str(e),
            "retryable": False
        }

    except Exception as e:

        return {
            "status": "error",
            "error_type": "tool_execution_error",
            "message": str(e),
            "retryable": False
        }
    
  
def load_tool_schemas():

    schema_path = os.path.join(
        "tools",
        "tool_schemas.json"
    )


    with open(
        schema_path,
        "r",
        encoding="utf-8"
    ) as f:

        return json.load(f)

def filter_tool_schemas(tool_names):

    schemas = load_tool_schemas()

    return [
        tool
        for tool in schemas
        if tool["name"] in tool_names
    ]

