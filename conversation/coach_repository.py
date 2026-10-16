"""Account-owned dialogue and learning anchors, independent of legacy journeys."""

import sqlite3
from contextlib import closing
from pathlib import Path
from time import time


PENDING_LIFETIME = 180
HISTORY_PAGE_SIZE = 40


class CoachRepository:
    def __init__(self, database_path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS coach_turns (
                    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    nonce TEXT NOT NULL,
                    user_content TEXT NOT NULL,
                    assistant_content TEXT,
                    status TEXT NOT NULL CHECK(status IN ('pending','complete','failed')),
                    created_at INTEGER NOT NULL,
                    completed_at INTEGER,
                    UNIQUE(user_id, nonce)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS coach_one_pending
                    ON coach_turns(user_id) WHERE status = 'pending';
                CREATE INDEX IF NOT EXISTS coach_history
                    ON coach_turns(user_id, turn_id DESC);
                CREATE TABLE IF NOT EXISTS coach_learning (
                    user_id TEXT PRIMARY KEY,
                    topic TEXT NOT NULL,
                    progress TEXT NOT NULL,
                    next_step TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                );
            """)

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _expire(connection, user_id, now):
        # Never automatically resend an interrupted provider request.
        connection.execute(
            "UPDATE coach_turns SET status='failed', completed_at=? "
            "WHERE user_id=? AND status='pending' AND created_at<=?",
            (now, user_id, now - PENDING_LIFETIME),
        )

    @staticmethod
    def _history_page(connection, user_id, before=None):
        rows = connection.execute(
            "SELECT turn_id, user_content, assistant_content, status, created_at "
            "FROM coach_turns WHERE user_id=? AND turn_id<? ORDER BY turn_id DESC LIMIT ?",
            (
                user_id,
                before if before is not None else 9223372036854775807,
                HISTORY_PAGE_SIZE + 1,
            ),
        ).fetchall()
        turns = [dict(row) for row in reversed(rows[:HISTORY_PAGE_SIZE])]
        return {
            "turns": turns,
            "before": turns[0]["turn_id"] if len(rows) > HISTORY_PAGE_SIZE else None,
        }

    def history_page(self, user_id, *, before):
        if type(before) is not int or not 1 <= before <= 9223372036854775807:
            raise ValueError("invalid history cursor")
        with closing(self._connect()) as connection:
            return self._history_page(connection, user_id, before)

    def view(self, user_id, *, now=None):
        now = int(time()) if now is None else now
        with closing(self._connect()) as connection, connection:
            self._expire(connection, user_id, now)
            page = self._history_page(connection, user_id)
            learning = connection.execute(
                "SELECT topic, progress, next_step, updated_at FROM coach_learning WHERE user_id=?",
                (user_id,),
            ).fetchone()
        return {**page, "learning": dict(learning) if learning else None}

    def claim(self, user_id, nonce, text, *, now):
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            self._expire(connection, user_id, now)
            existing = connection.execute(
                "SELECT status FROM coach_turns WHERE user_id=? AND nonce=?",
                (user_id, nonce),
            ).fetchone()
            if existing:
                return "duplicate"
            if connection.execute(
                "SELECT 1 FROM coach_turns WHERE user_id=? AND status='pending'",
                (user_id,),
            ).fetchone():
                return "busy"
            connection.execute(
                "INSERT INTO coach_turns(user_id,nonce,user_content,status,created_at) "
                "VALUES(?,?,?,'pending',?)",
                (user_id, nonce, text, now),
            )
        return "claimed"

    def finish(self, user_id, nonce, answer, learning, *, now):
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            changed = connection.execute(
                "UPDATE coach_turns SET status='complete', assistant_content=?, completed_at=? "
                "WHERE user_id=? AND nonce=? AND status='pending' AND created_at>?",
                (answer, now, user_id, nonce, now - PENDING_LIFETIME),
            ).rowcount
            if changed and learning is not None:
                connection.execute(
                    "INSERT INTO coach_learning(user_id,topic,progress,next_step,updated_at) "
                    "VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
                    "topic=excluded.topic,progress=excluded.progress,"
                    "next_step=excluded.next_step,updated_at=excluded.updated_at",
                    (
                        user_id,
                        learning["topic"],
                        learning["progress"],
                        learning["next_step"],
                        now,
                    ),
                )
        return bool(changed)

    def fail(self, user_id, nonce, *, now):
        with closing(self._connect()) as connection, connection:
            connection.execute(
                "UPDATE coach_turns SET status='failed', completed_at=? "
                "WHERE user_id=? AND nonce=? AND status='pending'",
                (now, user_id, nonce),
            )
