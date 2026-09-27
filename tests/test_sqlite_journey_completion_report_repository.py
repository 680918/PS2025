from learning.journey_completion_report import (
    JourneyCompletionReport,
)
from learning.sqlite_journey_completion_report_repository import (
    SQLiteJourneyCompletionReportRepository,
)


def test_sqlite_completion_report_repository_should_persist_report(
    tmp_path,
):
    database_path = tmp_path / "completion_reports.db"

    repository = SQLiteJourneyCompletionReportRepository(database_path)

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

    report = JourneyCompletionReport(
        journey_id="journey_001",
        user_id="user_001",
        summary=summary,
        commentary="学习趋势持续改善，已完成当前学习旅程。",
    )

    repository.save(report)

    # 重新创建 Repository，模拟应用重启后再次读取。
    reloaded_repository = SQLiteJourneyCompletionReportRepository(database_path)

    saved_report = reloaded_repository.get_by_journey_for_user(
        journey_id="journey_001",
        user_id="user_001",
    )

    assert saved_report is not None
    assert saved_report.report_id == report.report_id
    assert saved_report.journey_id == "journey_001"
    assert saved_report.user_id == "user_001"
    assert saved_report.summary == summary
    assert saved_report.commentary == "学习趋势持续改善，已完成当前学习旅程。"
