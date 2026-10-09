from memory.memory_conflict_detector import (
    detect_memory_conflict,
)


def test_memory_conflict_detector_should_detect_changed_content():
    existing = {
        "memory_type": "learning",
        "memory_key": "python-level",
        "content": ("The learner still needs Python fundamentals."),
    }

    incoming = {
        "memory_type": "learning",
        "memory_key": "python-level",
        "content": ("The learner has fully mastered Python."),
    }

    result = detect_memory_conflict(
        existing,
        incoming,
    )

    assert result == {
        "has_conflict": True,
        "reason": "same_slot_content_changed",
    }


def test_memory_conflict_detector_should_not_report_same_content():
    existing = {
        "memory_type": "learning",
        "memory_key": "python-level",
        "content": "Needs Python practice.",
    }

    incoming = {
        "memory_type": "learning",
        "memory_key": "python-level",
        "content": "Needs Python practice.",
    }

    result = detect_memory_conflict(
        existing,
        incoming,
    )

    assert result == {
        "has_conflict": False,
        "reason": "same_content",
    }


def test_memory_conflict_detector_should_ignore_different_memory_slots():
    existing = {
        "memory_type": "learning",
        "memory_key": "python-level",
        "content": "Needs Python practice.",
    }

    incoming = {
        "memory_type": "learning",
        "memory_key": "tool-calling-level",
        "content": "Tool Calling basics understood.",
    }

    result = detect_memory_conflict(
        existing,
        incoming,
    )

    assert result == {
        "has_conflict": False,
        "reason": "different_slot",
    }


def test_memory_conflict_detector_should_treat_whitespace_only_change_as_same():
    existing = {
        "memory_type": "learning",
        "memory_key": "python-level",
        "content": "Needs Python practice.",
    }

    incoming = {
        "memory_type": "learning",
        "memory_key": "python-level",
        "content": "  Needs Python practice.  ",
    }

    result = detect_memory_conflict(
        existing,
        incoming,
    )

    assert result == {
        "has_conflict": False,
        "reason": "same_content",
    }
