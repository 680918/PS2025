from learning.journey_completion_commentary_service import (
    generate_journey_completion_commentary_from_repositories,
)


def test_generate_journey_completion_commentary_from_repositories():
    class FakeJourney:
        journey_id = "journey_001"
        user_id = "user_001"
        domain = "Python"
        goal = "能够独立编写简单程序"
        status = "completed"

    class FakeJourneyRepository:
        def get_by_id_for_user(self, journey_id, user_id):
            return FakeJourney()

    class FakeSession:
        def __init__(self, session_id, score):
            self.session_id = session_id
            self.completed = True
            self.understanding_score = score

    class FakeSessionRepository:
        def list_by_journey_for_user(self, journey_id, user_id):
            return [
                FakeSession("session_001", 60),
                FakeSession("session_002", 85),
            ]

    class FakeEvidence:
        assessment = "已完成"
        tests_passed = 4
        tests_total = 4

    class FakeEvidenceRepository:
        def list_by_session(self, session_id):
            return [FakeEvidence()]

    class FakeCommentaryGenerator:
        def __init__(self):
            self.received_summary = None

        def generate(self, summary):
            self.received_summary = summary
            return "你的理解度从60提升到85，学习趋势持续改善。"

    generator = FakeCommentaryGenerator()

    commentary = generate_journey_completion_commentary_from_repositories(
        journey_repository=FakeJourneyRepository(),
        session_repository=FakeSessionRepository(),
        evidence_repository=FakeEvidenceRepository(),
        journey_id="journey_001",
        user_id="user_001",
        commentary_generator=generator,
    )

    assert commentary == "你的理解度从60提升到85，学习趋势持续改善。"

    assert generator.received_summary["domain"] == "Python"
    assert generator.received_summary["status"] == "completed"
    assert generator.received_summary["completed_sessions"] == 2
    assert generator.received_summary["first_understanding"] == 60
    assert generator.received_summary["latest_understanding"] == 85
    assert generator.received_summary["understanding_change"] == 25
    assert generator.received_summary["trend"] == "improving"
    assert generator.received_summary["evidence_count"] == 2
