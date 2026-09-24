import sqlite3
from datetime import datetime
from pathlib import Path

from learning.journey import LearningJourney


class SQLiteLearningJourneyRepository:
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
                CREATE TABLE IF NOT EXISTS learning_journeys (
                    journey_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def save(self, journey):
        with self._connect() as connection:
            self.save_with_connection(journey, connection)

    def save_with_connection(self, journey, connection):
        connection.execute(
            """
            INSERT INTO learning_journeys (
                journey_id,
                user_id,
                domain,
                goal,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(journey_id)
            DO UPDATE SET
                user_id = excluded.user_id,
                domain = excluded.domain,
                goal = excluded.goal,
                status = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                journey.journey_id,
                journey.user_id,
                journey.domain,
                journey.goal,
                journey.status,
                journey.created_at.isoformat(),
                journey.updated_at.isoformat(),
            ),
        )

    def get_by_id(
        self,
        journey_id,
    ):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    journey_id,
                    user_id,
                    domain,
                    goal,
                    status,
                    created_at,
                    updated_at
                FROM learning_journeys
                WHERE journey_id = ?
                """,
                (journey_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_journey(row)

    def get_by_id_for_user(
        self,
        journey_id,
        user_id,
    ):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    journey_id,
                    user_id,
                    domain,
                    goal,
                    status,
                    created_at,
                    updated_at
                FROM learning_journeys
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

        return self._row_to_journey(row)

    def list_by_user(
        self,
        user_id,
    ):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    journey_id,
                    user_id,
                    domain,
                    goal,
                    status,
                    created_at,
                    updated_at
                FROM learning_journeys
                WHERE user_id = ?
                ORDER BY created_at ASC
                """,
                (user_id,),
            ).fetchall()

        return [self._row_to_journey(row) for row in rows]

    def _row_to_journey(
        self,
        row,
    ):
        return LearningJourney(
            journey_id=row[0],
            user_id=row[1],
            domain=row[2],
            goal=row[3],
            status=row[4],
            created_at=datetime.fromisoformat(row[5]),
            updated_at=datetime.fromisoformat(row[6]),
        )
