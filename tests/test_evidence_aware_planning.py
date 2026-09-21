from planning.journey_planning_adapter import (
    build_journey_planning_decision,
)


def test_incomplete_evidence_should_inform_planning_without_advancing():
    continuity = {
        "topic": "Python 函数",
        "difficulty": "参数边界处理",
        "next_step": "继续完成边界测试",
    }

    evaluation = {
        "trend": "improving",
    }

    evidence_summary = {
        "evidence_count": 2,
        "completed_tasks": 1,
        "learning_signal": "insufficient_data",
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        evidence_summary=evidence_summary,
    )

    assert decision.topic == "Python 函数"
    assert decision.action == "continue"
    assert decision.next_topic is None
    assert "练习" in decision.reason
    assert "1/2" in decision.reason


def test_completed_evidence_should_not_automatically_advance():
    continuity = {
        "topic": "Python 函数",
        "difficulty": "参数边界处理",
        "next_step": "继续完成边界测试",
    }

    evaluation = {
        "trend": "improving",
    }

    evidence_summary = {
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        evidence_summary=evidence_summary,
    )

    assert decision.topic == "Python 函数"
    assert decision.action == "continue"
    assert decision.next_topic is None
    assert "2/2" in decision.reason


def test_empty_evidence_should_not_claim_completed_practice():
    continuity = {
        "topic": "Python 函数",
        "difficulty": "参数边界处理",
        "next_step": "继续完成边界测试",
    }

    evaluation = {
        "trend": "improving",
    }

    evidence_summary = {
        "evidence_count": 0,
        "completed_tasks": 0,
        "learning_signal": "insufficient_data",
    }

    decision = build_journey_planning_decision(
        continuity=continuity,
        evaluation=evaluation,
        evidence_summary=evidence_summary,
    )

    assert decision.action == "continue"
    assert decision.next_topic is None
    assert "0/0" not in decision.reason
    assert "全部完成" not in decision.reason
