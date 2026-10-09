from memory.memory_trust_guard import (
    should_include_memory_by_trust,
)


def test_trust_guard_should_reject_explicit_zero_confidence():
    memory = {
        "memory_key": "learning:false-mastery",
        "content": "The learner fully mastered Python.",
        "confidence": 0.0,
    }

    assert should_include_memory_by_trust(memory) is False


def test_trust_guard_should_allow_positive_confidence():
    memory = {
        "memory_key": "learning:python-progress",
        "content": "The learner needs more practice.",
        "confidence": 0.8,
    }

    assert should_include_memory_by_trust(memory) is True


def test_trust_guard_should_allow_legacy_memory_without_confidence():
    memory = {
        "memory_key": "learning:legacy",
        "content": "Legacy memory.",
    }

    assert should_include_memory_by_trust(memory) is True
