from dataclasses import dataclass

from evaluation.learning_evaluator import evaluate_learning_progress
from evaluation.skill_update_policy import should_update_skill
from evaluation.skill_updater import update_skill_from_evaluation
from planning.learning_planner import (
    build_next_learning_decision_from_evaluation,
)


@dataclass
class LearningEvaluationResult:
    learning_record: object
    evaluation: object
    skill_update_decision: object
    updated_skill: object | None
    next_learning_decision: object | None


def process_learning_evaluation(
    learning_service,
    memory_service,
    learning_record,
):
    learning_service.save(learning_record)

    evaluation = evaluate_learning_progress(
        learning_record.topic,
        learning_service,
    )

    decision = should_update_skill(evaluation)

    updated_skill = None

    if decision.allowed:
        updated_skill = update_skill_from_evaluation(
            memory_service,
            evaluation,
        )

    next_learning_decision = None

    if evaluation.status != "insufficient_data":
        next_learning_decision = build_next_learning_decision_from_evaluation(
            evaluation,
            memory_service=memory_service,
        )

    return LearningEvaluationResult(
        learning_record=learning_record,
        evaluation=evaluation,
        skill_update_decision=decision,
        updated_skill=updated_skill,
        next_learning_decision=next_learning_decision,
    )
