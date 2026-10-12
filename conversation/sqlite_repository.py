import sqlite3
from datetime import datetime
from pathlib import Path

from conversation.message import ConversationMessage


class SQLiteConversationRepository:
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
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    message_id TEXT PRIMARY KEY,
                    journey_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def save(self, message):
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO conversation_messages (
                    message_id,
                    journey_id,
                    user_id,
                    role,
                    content,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.journey_id,
                    message.user_id,
                    message.role,
                    message.content,
                    message.created_at.isoformat(),
                ),
            )

    def list_by_journey(
        self,
        journey_id,
        user_id,
    ):
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    message_id,
                    journey_id,
                    user_id,
                    role,
                    content,
                    created_at
                FROM conversation_messages
                WHERE journey_id = ?
                AND user_id = ?
                ORDER BY created_at ASC
                """,
                (
                    journey_id,
                    user_id,
                ),
            ).fetchall()

        return [
            ConversationMessage(
                message_id=row[0],
                journey_id=row[1],
                user_id=row[2],
                role=row[3],
                content=row[4],
                created_at=datetime.fromisoformat(row[5]),
            )
            for row in rows
        ]
