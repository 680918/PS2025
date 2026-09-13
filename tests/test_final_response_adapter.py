from coach.final_response_adapter import build_final_response_input


def test_build_final_response_input_should_only_expose_coach_response():
    tool_result = {
        "status": "success",
        "tool_name": "save_learning_feedback",
        "data": {
            "topic": "Python面向对象基础",
            "understanding": 99,
            "evaluation_status": "stable",
            "internal_field": "should_not_be_exposed",
            "coach_response": {
                "facts": [
                    "理解度自评99%",
                    "测验10/10",
                ],
                "assessment": {
                    "status": "stable",
                    "confidence": 0.85,
                    "current_understanding": 99,
                },
                "recommendation": {
                    "action": "advance",
                    "next_topic": "Tool Calling",
                    "reason": "Advance to the next skill.",
                },
            },
        },
    }

    result = build_final_response_input(tool_result)

    assert result["facts"] == [
        "理解度自评99%",
        "测验10/10",
    ]
    assert result["assessment"]["status"] == "stable"
    assert result["recommendation"]["next_topic"] == "Tool Calling"

    assert "topic" not in result
    assert "understanding" not in result
    assert "evaluation_status" not in result
    assert "internal_field" not in result


def test_build_final_response_input_should_support_tools_without_coach_response():
    tool_result = {
        "status": "success",
        "tool_name": "get_user_profile",
        "data": {
            "goal": "AI Agent",
        },
    }

    result = build_final_response_input(tool_result)

    assert result == {
        "tool_name": "get_user_profile",
        "status": "success",
        "data": {
            "goal": "AI Agent",
        },
    }


def test_profile_tool_should_only_expose_safe_fields():
    from coach.final_response_adapter import build_final_response_input

    tool_result = {
        "status": "success",
        "tool_name": "get_user_profile",
        "data": {
            "goal": "一年内掌握AI Agent应用搭建能力",
            "technical_level": "初学者",
            "learning_preferences": ["先理解原理", "再动手实践"],
            "age": 58,
            "internal_note": "should_not_be_exposed",
        },
    }

    result = build_final_response_input(tool_result)

    assert result["tool_name"] == "get_user_profile"
    assert result["status"] == "success"

    assert result["data"] == {
        "goal": "一年内掌握AI Agent应用搭建能力",
        "technical_level": "初学者",
        "learning_preferences": ["先理解原理", "再动手实践"],
    }

    assert "age" not in result["data"]
    assert "internal_note" not in result["data"]


def test_skill_map_tool_should_expose_skill_data():
    from coach.final_response_adapter import build_final_response_input

    tool_result = {
        "status": "success",
        "tool_name": "get_skill_map",
        "data": {
            "Python": {
                "level": 90,
            },
            "Tool Calling": {
                "level": 70,
            },
        },
    }

    result = build_final_response_input(tool_result)

    assert result["tool_name"] == "get_skill_map"
    assert result["status"] == "success"
    assert result["data"]["Python"]["level"] == 90
    assert result["data"]["Tool Calling"]["level"] == 70


def test_failed_tool_should_only_expose_safe_error_fields():
    from coach.final_response_adapter import build_final_response_input

    tool_result = {
        "status": "error",
        "tool_name": "save_learning_feedback",
        "error_type": "tool_execution_error",
        "message": "Failed to save learning feedback.",
        "retryable": False,
        "replannable": False,
        "internal_exception": "sqlite3.OperationalError: database is locked",
        "traceback": "very long internal traceback",
        "file_path": "D:\\personal-growth-coach\\data\\memory.db",
    }

    result = build_final_response_input(tool_result)

    assert result == {
        "status": "error",
        "tool_name": "save_learning_feedback",
        "error_type": "tool_execution_error",
        "message": "Failed to save learning feedback.",
    }

    assert "internal_exception" not in result
    assert "traceback" not in result
    assert "file_path" not in result
    assert "retryable" not in result
    assert "replannable" not in result
