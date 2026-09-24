import sqlite3
from pathlib import Path


class SQLiteJourneyCurriculumUnitOfWork:
    def __init__(
        self,
        database_path,
        journey_repository,
        curriculum_repository,
    ):
        self.database_path = Path(database_path)
        self.journey_repository = journey_repository
        self.curriculum_repository = curriculum_repository

    def save(self, journey, curriculum):
        curriculum_path = Path(self.curriculum_repository.database_path)

        separate_databases = curriculum_path.resolve() != self.database_path.resolve()

        with sqlite3.connect(self.database_path) as connection:
            if separate_databases:
                connection.execute(
                    "ATTACH DATABASE ? AS curriculum_db",
                    (str(curriculum_path),),
                )

                main_mode = (
                    connection.execute("PRAGMA main.journal_mode").fetchone()[0].lower()
                )

                curriculum_mode = (
                    connection.execute("PRAGMA curriculum_db.journal_mode")
                    .fetchone()[0]
                    .lower()
                )

                if main_mode == "wal" or curriculum_mode == "wal":
                    raise RuntimeError(
                        "WAL mode is not supported for cross-database atomic creation"
                    )

            self.journey_repository.save_with_connection(
                journey,
                connection,
            )

            self.curriculum_repository.save_with_connection(
                curriculum,
                connection,
            )
