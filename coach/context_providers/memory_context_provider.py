def build_memory_context(
    memory_service,
    user_message,
):
    if memory_service is None:
        return {}

    return memory_service.get_context()
