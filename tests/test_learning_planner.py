from planning.learning_planner import (
    LearningPlanDecision,
    decide_learning_action,
)


def test_high_confidence_improving_high_score_should_advance():
    result = decide_learning_action(
        topic="Python函数",
        understanding=96,
        status="improving",
        confidence=0.85,
    )

    assert isinstance(result, LearningPlanDecision)

    assert result.topic == "Python函数"
    assert result.action == "advance"
    assert result.reason


def test_improving_but_not_mastered_should_continue():
    result = decide_learning_action(
        topic="Python异常处理",
        understanding=70,
        status="improving",
        confidence=0.85,
    )

    assert isinstance(result, LearningPlanDecision)

    assert result.topic == "Python异常处理"
    assert result.action == "continue"
    assert result.reason


def test_stable_and_medium_high_understanding_should_review():
    from planning.learning_planner import decide_learning_action

    result = decide_learning_action(
        topic="Python函数",
        understanding=85,
        status="stable",
        confidence=0.85,
    )

    assert isinstance(result, LearningPlanDecision)

    assert result.topic == "Python函数"
    assert result.action == "review"
    assert result.reason


def test_declining_should_remediate():
    result = decide_learning_action(
        topic="Python函数",
        understanding=70,
        status="declining",
        confidence=0.85,
    )

    assert isinstance(result, LearningPlanDecision)

    assert result.topic == "Python函数"
    assert result.action == "remediate"
    assert result.reason


def test_low_confidence_should_continue_instead_of_advance():
    result = decide_learning_action(
        topic="Python函数",
        understanding=95,
        status="improving",
        confidence=0.4,
    )

    assert isinstance(result, LearningPlanDecision)

    assert result.topic == "Python函数"
    assert result.action == "continue"
    assert result.reason


def test_low_confidence_declining_should_not_remediate():
    result = decide_learning_action(
        topic="Python函数",
        understanding=60,
        status="declining",
        confidence=0.4,
    )

    assert isinstance(result, LearningPlanDecision)

    assert result.topic == "Python函数"
    assert result.action == "continue"
    assert result.reason


def test_build_next_learning_decision_for_advance():
    from planning.learning_planner import build_next_learning_decision

    result = build_next_learning_decision(
        topic="Python函数",
        understanding=96,
        status="improving",
        confidence=0.85,
    )

    assert result.topic == "Python函数"
    assert result.action == "advance"
    assert result.next_topic == "Python异常处理"
    assert result.reason


def test_continue_should_not_have_next_topic():
    from planning.learning_planner import build_next_learning_decision

    result = build_next_learning_decision(
        topic="Python函数",
        understanding=70,
        status="improving",
        confidence=0.85,
    )

    assert result.action == "continue"
    assert result.next_topic is None


def test_advance_at_end_of_learning_path_should_review():
    from planning.learning_planner import build_next_learning_decision

    result = build_next_learning_decision(
        topic="Python面向对象基础",
        understanding=95,
        status="improving",
        confidence=0.85,
    )

    assert result.action == "review"
    assert result.next_topic is None
    assert result.reason


def test_end_of_python_path_should_advance_to_next_skill():
    from planning.learning_planner import build_next_learning_decision

    result = build_next_learning_decision(
        topic="Python面向对象基础",
        understanding=95,
        status="improving",
        confidence=0.85,
        goal="AI Agent",
        current_skill="Python",
    )

    assert result.action == "advance"
    assert result.next_topic == "Tool Calling"
    assert result.reason


def test_end_of_final_skill_should_review():
    from planning.learning_planner import build_next_learning_decision

    result = build_next_learning_decision(
        topic="Python面向对象基础",
        understanding=95,
        status="improving",
        confidence=0.85,
        goal="AI Agent",
        current_skill="Agent Architecture",
    )

    assert result.action == "review"
    assert result.next_topic is None


def test_planner_should_resolve_current_skill_from_topic():
    from planning.learning_planner import build_next_learning_decision

    result = build_next_learning_decision(
        topic="Python面向对象基础",
        understanding=95,
        status="improving",
        confidence=0.85,
        goal="AI Agent",
    )

    assert result.action == "advance"
    assert result.next_topic == "Tool Calling"


def test_planner_should_resolve_goal_from_memory_service():
    from memory.service import MemoryService
    from memory.store import MemoryStore
    from planning.learning_planner import build_next_learning_decision

    store = MemoryStore()
    memory_service = MemoryService(store)

    memory_service.remember(
        memory_type="profile",
        memory_key="goal",
        content="AI Agent",
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    result = build_next_learning_decision(
        topic="Python面向对象基础",
        understanding=95,
        status="improving",
        confidence=0.85,
        memory_service=memory_service,
    )

    assert result.action == "advance"
    assert result.next_topic == "Tool Calling"


def test_build_decision_from_evaluation_result():
    from evaluation.learning_evaluator import LearningProgressResult
    from memory.service import MemoryService
    from memory.store import MemoryStore
    from planning.learning_planner import (
        build_next_learning_decision_from_evaluation,
    )

    store = MemoryStore()
    memory_service = MemoryService(store)

    memory_service.remember(
        memory_type="profile",
        memory_key="goal",
        content="AI Agent",
        importance=0.9,
        confidence=1.0,
        source="user_confirmed",
    )

    evaluation = LearningProgressResult(
        topic="Python面向对象基础",
        status="improving",
        previous_understanding=90,
        current_understanding=95,
        change=5,
        confidence=0.85,
        reason="Learning progress is improving.",
    )

    result = build_next_learning_decision_from_evaluation(
        evaluation,
        memory_service=memory_service,
    )

    assert result.action == "advance"
    assert result.next_topic == "Tool Calling"


def test_high_mastery_stable_should_advance():
    from planning.learning_planner import decide_learning_action

    result = decide_learning_action(
        topic="Python面向对象基础",
        understanding=95,
        status="stable",
        confidence=0.85,
    )

    assert result.action == "advance"


def test_medium_high_stable_should_review():
    from planning.learning_planner import decide_learning_action

    result = decide_learning_action(
        topic="Python面向对象基础",
        understanding=85,
        status="stable",
        confidence=0.85,
    )

    assert result.action == "review"


def test_high_mastery_stable_with_low_confidence_should_continue():
    from planning.learning_planner import decide_learning_action

    result = decide_learning_action(
        topic="Python面向对象基础",
        understanding=95,
        status="stable",
        confidence=0.4,
    )

    assert result.action == "continue"
