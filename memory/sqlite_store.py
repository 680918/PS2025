import sqlite3

from memory.models import MemoryRecord
from datetime import datetime


class SQLiteMemoryStore:
    def __init__(self, db_path):
        self.db_path = str(db_path)
        self._create_table()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _create_table(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    memory_key TEXT,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def add(self, memory: MemoryRecord):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                    id,
                    memory_type,
                    memory_key,
                    content,
                    importance,
                    confidence,
                    source,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.id,
                    memory.memory_type,
                    memory.memory_key,
                    memory.content,
                    memory.importance,
                    memory.confidence,
                    memory.source,
                    memory.created_at,
                    memory.updated_at,
                ),
            )

    def get(self, memory_id: str):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    memory_type,
                    memory_key,
                    content,
                    importance,
                    confidence,
                    source,
                    created_at,
                    updated_at
                FROM memories
                WHERE id = ?
                """,
                (memory_id,),
            ).fetchone()

        if row is None:
            return None

        return MemoryRecord(
            id=row[0],
            memory_type=row[1],
            memory_key=row[2],
            content=row[3],
            importance=row[4],
            confidence=row[5],
            source=row[6],
            created_at=row[7],
            updated_at=row[8],
        )

    def list_by_type(self, memory_type: str):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    memory_type,
                    memory_key,
                    content,
                    importance,
                    confidence,
                    source,
                    created_at,
                    updated_at
                FROM memories
                WHERE memory_type = ?
                """,
                (memory_type,),
            ).fetchall()

        return [
            MemoryRecord(
                id=row[0],
                memory_type=row[1],
                memory_key=row[2],
                content=row[3],
                importance=row[4],
                confidence=row[5],
                source=row[6],
                created_at=row[7],
                updated_at=row[8],
            )
            for row in rows
        ]

    def find_by_key(self, memory_type: str, memory_key: str):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    id,
                    memory_type,
                    memory_key,
                    content,
                    importance,
                    confidence,
                    source,
                    created_at,
                    updated_at
                FROM memories
                WHERE memory_type = ?
                AND memory_key = ?
                LIMIT 1
                """,
                (
                    memory_type,
                    memory_key,
                ),
            ).fetchone()

        if row is None:
            return None

        return MemoryRecord(
            id=row[0],
            memory_type=row[1],
            memory_key=row[2],
            content=row[3],
            importance=row[4],
            confidence=row[5],
            source=row[6],
            created_at=row[7],
            updated_at=row[8],
        )

    def update(self, memory_id: str, **changes):
        memory = self.get(memory_id)

        if memory is None:
            return None

        allowed_fields = {
            "content",
            "importance",
            "confidence",
            "source",
            "memory_key",
        }

        for field in changes:
            if field not in allowed_fields:
                raise ValueError(f"Field cannot be updated: {field}")

        for field, value in changes.items():
            setattr(memory, field, value)

        memory.validate()
        memory.updated_at = datetime.now().isoformat()

        with self._connect() as conn:
            conn.execute(
                """
                UPDATE memories
                SET
                    memory_key = ?,
                    content = ?,
                    importance = ?,
                    confidence = ?,
                    source = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    memory.memory_key,
                    memory.content,
                    memory.importance,
                    memory.confidence,
                    memory.source,
                    memory.updated_at,
                    memory.id,
                ),
            )

        return memory
