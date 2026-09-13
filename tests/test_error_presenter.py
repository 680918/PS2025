from coach.error_presenter import (
    present_final_response_error,
    present_runtime_error,
)


class FakeState:
    def __init__(self, error=None):
        self.error = error


def test_tool_execution_error_should_be_presented_safely():
    state = FakeState(
        error={
            "error_type": "tool_execution_error",
            "message": "sqlite3.OperationalError: database is locked",
            "traceback": "SECRET_TRACEBACK",
        }
    )

    result = present_runtime_error(state)

    assert result.title == "操作失败"
    assert result.retry_suggested is True

    assert "sqlite3" not in result.message
    assert "database is locked" not in result.message
    assert "SECRET_TRACEBACK" not in result.message


def test_unknown_error_should_use_generic_message():
    state = FakeState(
        error={
            "error_type": "unknown_error",
        }
    )

    result = present_runtime_error(state)

    assert result.title == "任务未完成"
    assert result.retry_suggested is True


def test_final_response_error_should_be_safe():
    result = present_final_response_error()

    assert result.title == "回答生成失败"
    assert result.retry_suggested is True
    assert "最终回答" in result.message


def test_final_response_error_should_not_claim_runtime_failed():
    result = present_final_response_error()

    assert "任务未完成" not in result.message
    assert "工具执行失败" not in result.message
