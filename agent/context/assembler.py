def assemble_context(
    contexts,
):

    return {key: value for key, value in contexts.items() if value is not None}
