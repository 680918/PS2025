def make_error(
    error_type,
    message,
    retryable=False,
    replannable=False,
    content=None,
):

    if not error_type:
        raise ValueError("error_type must not be empty")

    if not message:
        raise ValueError("message must not be empty")

    return {
        "status": "error",
        "error_type": error_type,
        "message": message,
        "content": content,
        "retryable": retryable,
        "replannable": replannable,
    }
