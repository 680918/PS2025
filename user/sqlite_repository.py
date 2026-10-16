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
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

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

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_passwords (
                    user_id TEXT PRIMARY KEY NOT NULL,
                    password_hash TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
                """
            )

    def save_initial_password_hash(self, user_id, password_hash):
        """Store only a hash for an existing user, without replacing credentials."""
        if not isinstance(password_hash, str) or not password_hash.startswith(
            "$argon2id$"
        ):
            raise ValueError("an Argon2id password hash is required")

        with self._connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO user_passwords (user_id, password_hash)
                    SELECT user_id, ? FROM users WHERE user_id = ?
                    """,
                    (password_hash, user_id),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("password already initialized") from error
            if cursor.rowcount != 1:
                raise ValueError("user not found")

    def get_password_hash(self, user_id):
        """Credential access is explicit; normal User objects never contain hashes."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT password_hash FROM user_passwords WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row[0] if row else None

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
