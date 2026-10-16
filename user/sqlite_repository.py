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

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS user_email_verifications (
                    user_id TEXT PRIMARY KEY NOT NULL,
                    email TEXT NOT NULL,
                    token_hash TEXT UNIQUE,
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL CHECK (expires_at > issued_at),
                    verified_at INTEGER,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    CHECK (token_hash IS NULL OR length(token_hash) = 64)
                )
                """
            )

    def issue_email_verification_token(
        self, user_id, token_hash, issued_at, expires_at, resend_interval
    ):
        """Replace a pending token atomically, binding it to the current stored email."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            user = connection.execute(
                "SELECT email FROM users WHERE user_id = ?", (user_id,)
            ).fetchone()
            if user is None:
                raise ValueError("email verification unavailable")
            email = user[0]
            previous = connection.execute(
                """
                SELECT email, issued_at, verified_at
                FROM user_email_verifications WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
            if previous is not None and (
                (previous[0] == email and previous[2] is not None)
                or issued_at < previous[1] + resend_interval
            ):
                raise ValueError("email verification unavailable")
            connection.execute(
                """
                INSERT INTO user_email_verifications (
                    user_id, email, token_hash, issued_at, expires_at, verified_at
                ) VALUES (?, ?, ?, ?, ?, NULL)
                ON CONFLICT(user_id) DO UPDATE SET
                    email = excluded.email,
                    token_hash = excluded.token_hash,
                    issued_at = excluded.issued_at,
                    expires_at = excluded.expires_at,
                    verified_at = NULL
                """,
                (user_id, email, token_hash, issued_at, expires_at),
            )
        return email

    def consume_email_verification_token(self, token_hash, now):
        """Consume and mark verified in the same transaction, including concurrent use."""
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT verification.user_id
                FROM user_email_verifications AS verification
                JOIN users ON users.user_id = verification.user_id
                WHERE verification.token_hash = ?
                  AND verification.verified_at IS NULL
                  AND verification.issued_at <= ?
                  AND verification.expires_at > ?
                  AND verification.email = users.email
                """,
                (token_hash, now, now),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                """
                UPDATE user_email_verifications
                SET token_hash = NULL, verified_at = ?
                WHERE user_id = ? AND token_hash = ?
                """,
                (now, row[0], token_hash),
            )
            return row[0]

    def is_email_verified(self, user_id):
        """The flag is valid only for the same email that was actually verified."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM user_email_verifications AS verification
                JOIN users ON users.user_id = verification.user_id
                WHERE verification.user_id = ?
                  AND verification.email = users.email
                  AND verification.verified_at IS NOT NULL
                """,
                (user_id,),
            ).fetchone()
        return row is not None

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
