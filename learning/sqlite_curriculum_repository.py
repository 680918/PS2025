import sqlite3
from pathlib import Path

from learning.curriculum import CurriculumItem, LearningCurriculum


class SQLiteLearningCurriculumRepository:
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
                CREATE TABLE IF NOT EXISTS learning_curriculums (
                    journey_id TEXT PRIMARY KEY
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS learning_curriculum_items (
                    journey_id TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    PRIMARY KEY (journey_id, position)
                )
                """
            )

    def save(self, curriculum):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO learning_curriculums (journey_id)
                VALUES (?)
                ON CONFLICT(journey_id) DO NOTHING
                """,
                (curriculum.journey_id,),
            )

            connection.execute(
                """
                DELETE FROM learning_curriculum_items
                WHERE journey_id = ?
                """,
                (curriculum.journey_id,),
            )

            connection.executemany(
                """
                INSERT INTO learning_curriculum_items (
                    journey_id,
                    position,
                    topic
                )
                VALUES (?, ?, ?)
                """,
                [
                    (
                        curriculum.journey_id,
                        item.position,
                        item.topic,
                    )
                    for item in curriculum.items
                ],
            )

    def get_by_journey_id(self, journey_id):
        with self._connect() as connection:
            curriculum_row = connection.execute(
                """
                SELECT journey_id
                FROM learning_curriculums
                WHERE journey_id = ?
                """,
                (journey_id,),
            ).fetchone()

            if curriculum_row is None:
                return None

            item_rows = connection.execute(
                """
                SELECT position, topic
                FROM learning_curriculum_items
                WHERE journey_id = ?
                ORDER BY position ASC
                """,
                (journey_id,),
            ).fetchall()

        return LearningCurriculum(
            journey_id=curriculum_row[0],
            items=[
                CurriculumItem(
                    position=row[0],
                    topic=row[1],
                )
                for row in item_rows
            ],
        )
