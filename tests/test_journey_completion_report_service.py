from learning.journey_completion_report_service import (
    get_or_create_journey_completion_report,
)


def test_get_or_create_completion_report_should_generate_only_once():
    class FakeReportRepository:
        def __init__(self):
            self.report = None

        def get_by_journey_for_user(
            self,
            journey_id,
            user_id,
        ):
            return self.report

        def save(self, report):
            self.report = report

    class FakeCommentaryGenerator:
        def __init__(self):
            self.calls = 0

        def generate(self, summary):
            self.calls += 1
            return "学习趋势持续改善，已完成当前学习旅程。"

    summary = {
        "journey_id": "journey_001",
        "domain": "Python",
        "goal": "完成 Python 基础学习",
        "status": "completed",
        "completed_sessions": 2,
        "first_understanding": 60,
        "latest_understanding": 85,
        "understanding_change": 25,
        "trend": "improving",
        "evidence_count": 2,
        "completed_tasks": 2,
        "learning_signal": "positive",
        "quality_summary": {
            "strong": 2,
            "weak": 0,
            "insufficient": 0,
        },
    }

    repository = FakeReportRepository()
    generator = FakeCommentaryGenerator()

    first_report = get_or_create_journey_completion_report(
        repository=repository,
        summary=summary,
        user_id="user_001",
        commentary_generator=generator,
    )

    second_report = get_or_create_journey_completion_report(
        repository=repository,
        summary=summary,
        user_id="user_001",
        commentary_generator=generator,
    )

    assert first_report.report_id == second_report.report_id

    assert first_report.journey_id == "journey_001"
    assert first_report.user_id == "user_001"
    assert first_report.summary == summary
    assert first_report.commentary == "学习趋势持续改善，已完成当前学习旅程。"

    assert generator.calls == 1
