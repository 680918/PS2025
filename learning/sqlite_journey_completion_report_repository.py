import json
import sqlite3
from pathlib import Path

from learning.journey_completion_report import (
    JourneyCompletionReport,
)


class SQLiteJourneyCompletionReportRepository:
    def __init__(self, database_path):
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_database()

    def _connect(self):
        return sqlite3.connect(self.database_path)

    def _initialize_database(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS journey_completion_reports (
                    report_id TEXT PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    summary_json TEXT NOT NULL,
                    commentary TEXT NOT NULL,
                    UNIQUE(journey_id, user_id)
                )
                """
            )

    def save(self, report):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO journey_completion_reports (
                    report_id,
                    journey_id,
                    user_id,
                    summary_json,
                    commentary
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    report.report_id,
                    report.journey_id,
                    report.user_id,
                    json.dumps(
                        report.summary,
                        ensure_ascii=False,
                    ),
                    report.commentary,
                ),
            )

    def get_by_journey_for_user(
        self,
        journey_id,
        user_id,
    ):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    report_id,
                    journey_id,
                    user_id,
                    summary_json,
                    commentary
                FROM journey_completion_reports
                WHERE journey_id = ?
                AND user_id = ?
                """,
                (
                    journey_id,
                    user_id,
                ),
            ).fetchone()

        if row is None:
            return None

        return JourneyCompletionReport(
            report_id=row[0],
            journey_id=row[1],
            user_id=row[2],
            summary=json.loads(row[3]),
            commentary=row[4],
        )
