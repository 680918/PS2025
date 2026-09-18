import sqlite3
from pathlib import Path

from user.model import User


class SQLiteUserRepository:
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
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE
                )
                """
            )

    def save(self, user):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    user_id,
                    name,
                    email
                )
                VALUES (?, ?, ?)
                """,
                (
                    user.user_id,
                    user.name,
                    user.email,
                ),
            )

    def get_by_id(self, user_id):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    name,
                    email
                FROM users
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()

        if row is None:
            return None

        return User(
            user_id=row[0],
            name=row[1],
            email=row[2],
        )

    def get_by_email(self, email):
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    name,
                    email
                FROM users
                WHERE email = ?
                """,
                (email,),
            ).fetchone()

        if row is None:
            return None

        return User(
            user_id=row[0],
            name=row[1],
            email=row[2],
        )
