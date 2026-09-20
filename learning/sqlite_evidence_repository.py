import sqlite3
from pathlib import Path

from learning.evidence import LearningEvidence


class SQLiteLearningEvidenceRepository:
    def __init__(self, database_path):
        self.database_path = Path(database_path)

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize_database()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_database(self):
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_evidence (
                    evidence_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    task TEXT NOT NULL,
                    result TEXT NOT NULL,
                    assessment TEXT NOT NULL,
                    tests_passed INTEGER,
                    tests_total INTEGER,
                    FOREIGN KEY (session_id)
                        REFERENCES learning_sessions(session_id)
                )
                """
            )
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(learning_evidence)"
                ).fetchall()
            }

            if "tests_passed" not in columns:
                connection.execute(
                    "ALTER TABLE learning_evidence ADD COLUMN tests_passed INTEGER"
                )

            if "tests_total" not in columns:
                connection.execute(
                    "ALTER TABLE learning_evidence ADD COLUMN tests_total INTEGER"
                )

    def save(self, evidence):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO learning_evidence (
                    evidence_id,
                    session_id,
                    task,
                    result,
                    assessment,
                    tests_passed,
                    tests_total
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(evidence_id)
                DO UPDATE SET
                    session_id = excluded.session_id,
                    task = excluded.task,
                    result = excluded.result,
                    assessment = excluded.assessment,
                    tests_passed = excluded.tests_passed,
                    tests_total = excluded.tests_total
                """,
                (
                    evidence.evidence_id,
                    evidence.session_id,
                    evidence.task,
                    evidence.result,
                    evidence.assessment,
                    evidence.tests_passed,
                    evidence.tests_total,
                ),
            )

    def list_by_session(
        self,
        session_id,
    ):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    evidence_id,
                    session_id,
                    task,
                    result,
                    assessment,
                    tests_passed,
                    tests_total
                FROM learning_evidence
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchall()

        return [
            LearningEvidence(
                session_id=row[1],
                task=row[2],
                result=row[3],
                assessment=row[4],
                evidence_id=row[0],
                tests_passed=row[5],
                tests_total=row[6],
            )
            for row in rows
        ]
