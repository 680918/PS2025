import sqlite3
from contextlib import closing
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

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_registrations (
                    request_id TEXT PRIMARY KEY NOT NULL CHECK (length(request_id) = 45),
                    name TEXT NOT NULL CHECK (length(name) BETWEEN 1 AND 40),
                    email TEXT NOT NULL UNIQUE CHECK (email = lower(trim(email))),
                    password_hash TEXT NOT NULL CHECK (password_hash LIKE '$argon2id$%'),
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL CHECK (expires_at > created_at)
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS registration_email_verifications (
                    request_id TEXT PRIMARY KEY NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE CHECK (length(token_hash) = 64),
                    issued_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL CHECK (expires_at > issued_at),
                    FOREIGN KEY (request_id) REFERENCES pending_registrations (request_id)
                        ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS registration_browser_bindings (
                    request_id TEXT PRIMARY KEY NOT NULL,
                    token_hash TEXT NOT NULL UNIQUE CHECK (
                        length(token_hash) = 64 AND token_hash NOT GLOB '*[^0-9a-f]*'
                    ),
                    FOREIGN KEY (request_id) REFERENCES pending_registrations (request_id)
                        ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS registration_mail_deliveries (
                    request_id TEXT PRIMARY KEY NOT NULL,
                    attempt_id TEXT NOT NULL UNIQUE CHECK (
                        length(attempt_id) = 32 AND attempt_id NOT GLOB '*[^0-9a-f]*'
                    ),
                    state TEXT NOT NULL CHECK (
                        state IN ('sending', 'accepted', 'failed', 'unknown')
                    ),
                    FOREIGN KEY (request_id) REFERENCES pending_registrations (request_id)
                        ON DELETE CASCADE
                )
                """
            )

    def save_pending_registration(
        self,
        *,
        request_id,
        name,
        email,
        password_hash,
        created_at,
        expires_at,
        browser_token_hash=None,
    ):
        """Insert a draft atomically; never replace an active draft or user."""
        if not isinstance(password_hash, str) or not password_hash.startswith(
            "$argon2id$"
        ):
            raise ValueError("an Argon2id password hash is required")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "DELETE FROM pending_registrations WHERE expires_at <= ?", (created_at,)
            )
            if (
                connection.execute(
                    "SELECT 1 FROM users WHERE lower(trim(email)) = ?", (email,)
                ).fetchone()
                is not None
            ):
                raise ValueError("registration request unavailable")
            try:
                connection.execute(
                    """
                    INSERT INTO pending_registrations
                        (request_id, name, email, password_hash, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (request_id, name, email, password_hash, created_at, expires_at),
                )
                if browser_token_hash is not None:
                    connection.execute(
                        "INSERT INTO registration_browser_bindings (request_id, token_hash) VALUES (?, ?)",
                        (request_id, browser_token_hash),
                    )
            except sqlite3.IntegrityError:
                raise ValueError("registration request unavailable") from None

    def get_pending_registration(self, request_id, now):
        """Read secrets only for trusted internal callers; not a user profile."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            # Lazy cleanup avoids retaining expired draft hashes indefinitely
            # during normal use, without a background scheduler.
            connection.execute(
                """
                DELETE FROM pending_registrations
                WHERE expires_at <= ? OR EXISTS (
                    SELECT 1 FROM users
                    WHERE lower(trim(users.email)) = pending_registrations.email
                )
                """,
                (now,),
            )
            return connection.execute(
                """
                SELECT request_id, name, email, password_hash, created_at, expires_at
                FROM pending_registrations
                WHERE request_id = ? AND created_at <= ? AND expires_at > ?
                  AND NOT EXISTS (
                    SELECT 1 FROM registration_browser_bindings AS binding
                    WHERE binding.request_id = pending_registrations.request_id
                  )
                """,
                (request_id, now, now),
            ).fetchone()

    def get_browser_registration(self, request_id, browser_token_hash, now):
        """Authorize a minimal status read using the bound credential digest."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                DELETE FROM pending_registrations
                WHERE expires_at <= ? OR EXISTS (
                    SELECT 1 FROM users
                    WHERE lower(trim(users.email)) = pending_registrations.email
                )
                """,
                (now,),
            )
            return connection.execute(
                """
                SELECT draft.request_id, draft.expires_at, draft.email
                FROM pending_registrations AS draft
                JOIN registration_browser_bindings AS binding
                  ON binding.request_id = draft.request_id
                WHERE draft.request_id = ? AND binding.token_hash = ?
                  AND draft.created_at <= ? AND draft.expires_at > ?
                """,
                (request_id, browser_token_hash, now, now),
            ).fetchone()

    def issue_registration_verification_token(
        self,
        *,
        request_id,
        token_hash,
        issued_at,
        lifetime,
        resend_interval,
        browser_token_hash=None,
        delivery_attempt_id=None,
        retry_failed=False,
    ):
        """Bind a token to an immutable draft; resend never extends its lifetime."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT email, expires_at FROM pending_registrations AS draft
                WHERE request_id = ? AND created_at <= ? AND expires_at > ?
                  AND NOT EXISTS (
                    SELECT 1 FROM users WHERE lower(trim(users.email)) = draft.email
                  )
                  AND (
                    (? IS NULL AND NOT EXISTS (
                      SELECT 1 FROM registration_browser_bindings AS binding
                      WHERE binding.request_id = draft.request_id
                    )) OR EXISTS (
                      SELECT 1 FROM registration_browser_bindings AS binding
                      WHERE binding.request_id = draft.request_id AND binding.token_hash = ?
                    )
                  )
                """,
                (
                    request_id,
                    issued_at,
                    issued_at,
                    browser_token_hash,
                    browser_token_hash,
                ),
            ).fetchone()
            previous = connection.execute(
                "SELECT issued_at FROM registration_email_verifications WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            delivery = connection.execute(
                "SELECT state FROM registration_mail_deliveries WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if (
                row is None
                or (previous is not None and issued_at < previous[0] + resend_interval)
                or (
                    delivery is not None
                    and not (
                        delivery_attempt_id is not None
                        and retry_failed is True
                        and delivery[0] == "failed"
                    )
                )
                or (delivery is None and retry_failed)
            ):
                raise ValueError("registration verification unavailable")
            if delivery_attempt_id is not None and browser_token_hash is None:
                raise ValueError("registration verification unavailable")
            expires_at = min(row[1], issued_at + lifetime)
            connection.execute(
                """
                INSERT INTO registration_email_verifications
                    (request_id, token_hash, issued_at, expires_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(request_id) DO UPDATE SET
                    token_hash = excluded.token_hash,
                    issued_at = excluded.issued_at,
                    expires_at = excluded.expires_at
                """,
                (request_id, token_hash, issued_at, expires_at),
            )
            if delivery_attempt_id is not None:
                connection.execute(
                    """
                    INSERT INTO registration_mail_deliveries (request_id, attempt_id, state)
                    VALUES (?, ?, 'sending')
                    ON CONFLICT(request_id) DO UPDATE SET
                        attempt_id = excluded.attempt_id, state = 'sending'
                    """,
                    (request_id, delivery_attempt_id),
                )
            return row[0], expires_at

    def finish_registration_delivery(self, request_id, attempt_id, state):
        """Only the active worker may finish its own durable claim."""
        if state not in {"accepted", "failed", "unknown"}:
            raise ValueError("invalid delivery state")
        with closing(self._connect()) as connection, connection:
            cursor = connection.execute(
                """
                UPDATE registration_mail_deliveries SET state = ?
                WHERE request_id = ? AND attempt_id = ? AND state = 'sending'
                """,
                (state, request_id, attempt_id),
            )
            return cursor.rowcount == 1

    def get_registration_delivery_status(self, request_id, browser_token_hash, now):
        """Return only a state, with the same owner and lifetime checks as the draft."""
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT coalesce(delivery.state, 'not_sent')
                FROM pending_registrations AS draft
                JOIN registration_browser_bindings AS binding
                    ON binding.request_id = draft.request_id
                LEFT JOIN registration_mail_deliveries AS delivery
                    ON delivery.request_id = draft.request_id
                WHERE draft.request_id = ? AND binding.token_hash = ?
                    AND draft.created_at <= ? AND draft.expires_at > ?
                    AND NOT EXISTS (
                        SELECT 1 FROM users WHERE lower(trim(users.email)) = draft.email
                    )
                """,
                (request_id, browser_token_hash, now, now),
            ).fetchone()
            return row[0] if row is not None else None

    def consume_registration_verification_token(self, *, token_hash, now, user_id):
        """Create user, credentials and verified flag together, or roll back all."""
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                """
                DELETE FROM pending_registrations
                WHERE expires_at <= ? OR EXISTS (
                    SELECT 1 FROM users
                    WHERE lower(trim(users.email)) = pending_registrations.email
                )
                """,
                (now,),
            )
            row = connection.execute(
                """
                SELECT draft.request_id, draft.name, draft.email, draft.password_hash,
                       verification.issued_at, verification.expires_at
                FROM pending_registrations AS draft
                JOIN registration_email_verifications AS verification
                  ON verification.request_id = draft.request_id
                WHERE verification.token_hash = ?
                  AND verification.issued_at <= ? AND verification.expires_at > ?
                  AND draft.created_at <= ? AND draft.expires_at > ?
                """,
                (token_hash, now, now, now, now),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "INSERT INTO users (user_id, name, email) VALUES (?, ?, ?)",
                (user_id, row[1], row[2]),
            )
            connection.execute(
                "INSERT INTO user_passwords (user_id, password_hash) VALUES (?, ?)",
                (user_id, row[3]),
            )
            connection.execute(
                """
                INSERT INTO user_email_verifications
                    (user_id, email, token_hash, issued_at, expires_at, verified_at)
                VALUES (?, ?, NULL, ?, ?, ?)
                """,
                (user_id, row[2], row[4], row[5], now),
            )
            connection.execute(
                "DELETE FROM pending_registrations WHERE request_id = ?", (row[0],)
            )
            return user_id

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
