from coach.response_contract import (
    CoachResponseContract,
    build_coach_response_contract,
)
from evaluation.learning_evaluator import LearningProgressResult
from memory.learning_models import LearningRecord
from planning.learning_planner import LearningPlanDecision


def test_coach_response_contract_should_separate_response_layers():
    contract = CoachResponseContract(
        facts=[
            "理解度自评99%",
            "测验得分10/10",
        ],
        assessment={
            "status": "stable",
            "confidence": 0.85,
            "current_understanding": 99,
        },
        recommendation={
            "action": "advance",
            "next_topic": "Tool Calling",
            "reason": "Advance to the next skill in the goal path.",
        },
    )

    assert contract.facts == [
        "理解度自评99%",
        "测验得分10/10",
    ]

    assert contract.assessment["status"] == "stable"
    assert contract.assessment["confidence"] == 0.85
    assert contract.assessment["current_understanding"] == 99

    assert contract.recommendation["action"] == "advance"
    assert contract.recommendation["next_topic"] == "Tool Calling"
    assert contract.recommendation["reason"] == (
        "Advance to the next skill in the goal path."
    )


def test_build_coach_response_contract_from_learning_results():
    learning_record = LearningRecord(
        topic="Python面向对象基础",
        understanding=99,
        evidence="测验10/10",
        evidence_type="quiz",
    )

    evaluation = LearningProgressResult(
        topic="Python面向对象基础",
        status="stable",
        previous_understanding=99,
        current_understanding=99,
        change=0,
        confidence=0.85,
        reason="Recent learning performance is stable.",
    )

    planning_decision = LearningPlanDecision(
        topic="Python面向对象基础",
        action="advance",
        reason="Advance to the next skill in the goal path.",
        next_topic="Tool Calling",
    )

    contract = build_coach_response_contract(
        learning_record=learning_record,
        evaluation=evaluation,
        planning_decision=planning_decision,
    )

    assert "理解度自评99%" in contract.facts
    assert "测验10/10" in contract.facts

    assert isinstance(contract.assessment, dict)
    assert contract.assessment["status"] == "stable"
    assert contract.assessment["confidence"] == 0.85
    assert contract.assessment["current_understanding"] == 99

    assert isinstance(contract.recommendation, dict)
    assert contract.recommendation["action"] == "advance"
    assert contract.recommendation["next_topic"] == "Tool Calling"
    assert contract.recommendation["reason"] == (
        "Advance to the next skill in the goal path."
    )
