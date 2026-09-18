import sqlite3
from datetime import datetime
from pathlib import Path

from learning.session import LearningSession


class SQLiteLearningSessionRepository:
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
                CREATE TABLE IF NOT EXISTS learning_sessions (
                    session_id TEXT PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    completed INTEGER NOT NULL,
                    understanding_score INTEGER,
                    difficulty TEXT,
                    next_step TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save(self, session):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO learning_sessions (
                    session_id,
                    journey_id,
                    user_id,
                    topic,
                    completed,
                    understanding_score,
                    difficulty,
                    next_step,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.journey_id,
                    session.user_id,
                    session.topic,
                    int(session.completed),
                    session.understanding_score,
                    session.difficulty,
                    session.next_step,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )

    def get_latest_by_journey(
        self,
        journey_id,
    ):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    session_id,
                    journey_id,
                    user_id,
                    topic,
                    completed,
                    understanding_score,
                    difficulty,
                    next_step,
                    created_at,
                    updated_at
                FROM learning_sessions
                WHERE journey_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (journey_id,),
            ).fetchone()

        if row is None:
            return None

        return LearningSession(
            session_id=row[0],
            journey_id=row[1],
            user_id=row[2],
            topic=row[3],
            completed=bool(row[4]),
            understanding_score=row[5],
            difficulty=row[6],
            next_step=row[7],
            created_at=datetime.fromisoformat(row[8]),
            updated_at=datetime.fromisoformat(row[9]),
        )
