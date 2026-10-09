def should_include_memory_by_trust(
    memory,
):
    if "confidence" not in memory:
        return True

    confidence = memory["confidence"]

    if isinstance(
        confidence,
        bool,
    ):
        return False

    if not isinstance(
        confidence,
        (int, float),
    ):
        return False

    if not 0 <= confidence <= 1:
        return False

    return confidence > 0.0
