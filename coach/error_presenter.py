from dataclasses import dataclass


@dataclass
class UserFacingError:
    title: str
    message: str
    retry_suggested: bool = False


def present_runtime_error(state):
    error = getattr(state, "error", None)

    if not error:
        error = getattr(state, "last_result", None)

    if not error:
        return UserFacingError(
            title="任务未完成",
            message="这次操作没有成功完成。",
            retry_suggested=True,
        )

    error_type = error.get("error_type")

    if error_type == "tool_execution_error":
        return UserFacingError(
            title="操作失败",
            message="工具执行时出现问题，这次操作没有成功完成。",
            retry_suggested=True,
        )

    return UserFacingError(
        title="任务未完成",
        message="这次操作没有成功完成。",
        retry_suggested=True,
    )


def present_final_response_error():
    return UserFacingError(
        title="回答生成失败",
        message="任务已经完成处理，但最终回答暂时无法生成。",
        retry_suggested=True,
    )
