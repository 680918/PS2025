import sqlite3


class SQLiteMemoryReliabilityRunRecordStore:
    def __init__(
        self,
        db_path,
    ):
        self.db_path = str(db_path)
        self._create_table()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _create_table(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS
                memory_reliability_run_records (
                    run_id TEXT PRIMARY KEY,
                    schema_version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    candidates INTEGER NOT NULL,
                    blocked_by_trust INTEGER NOT NULL,
                    trusted_candidates INTEGER NOT NULL,
                    not_selected_before_budget INTEGER NOT NULL,
                    selected_before_budget INTEGER NOT NULL,
                    removed_by_budget INTEGER NOT NULL,
                    injected INTEGER NOT NULL
                )
                """
            )

    def save(
        self,
        record,
    ):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO
                memory_reliability_run_records (
                    run_id,
                    schema_version,
                    created_at,
                    candidates,
                    blocked_by_trust,
                    trusted_candidates,
                    not_selected_before_budget,
                    selected_before_budget,
                    removed_by_budget,
                    injected
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    record["run_id"],
                    record["schema_version"],
                    record["created_at"],
                    record["candidates"],
                    record["blocked_by_trust"],
                    record["trusted_candidates"],
                    record["not_selected_before_budget"],
                    record["selected_before_budget"],
                    record["removed_by_budget"],
                    record["injected"],
                ),
            )

    def list_all(
        self,
    ):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    schema_version,
                    run_id,
                    created_at,
                    candidates,
                    blocked_by_trust,
                    trusted_candidates,
                    not_selected_before_budget,
                    selected_before_budget,
                    removed_by_budget,
                    injected
                FROM
                    memory_reliability_run_records
                ORDER BY
                    created_at ASC,
                    run_id ASC
                """
            ).fetchall()

        return [
            {
                "schema_version": row[0],
                "run_id": row[1],
                "created_at": row[2],
                "candidates": row[3],
                "blocked_by_trust": row[4],
                "trusted_candidates": row[5],
                "not_selected_before_budget": (row[6]),
                "selected_before_budget": (row[7]),
                "removed_by_budget": row[8],
                "injected": row[9],
            }
            for row in rows
        ]

    def list_recent(
        self,
        limit,
    ):
        if limit <= 0:
            raise ValueError("limit must be positive")

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    schema_version,
                    run_id,
                    created_at,
                    candidates,
                    blocked_by_trust,
                    trusted_candidates,
                    not_selected_before_budget,
                    selected_before_budget,
                    removed_by_budget,
                    injected
                FROM
                    memory_reliability_run_records
                ORDER BY
                    created_at DESC,
                    run_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        rows.reverse()

        return [
            {
                "schema_version": row[0],
                "run_id": row[1],
                "created_at": row[2],
                "candidates": row[3],
                "blocked_by_trust": row[4],
                "trusted_candidates": row[5],
                "not_selected_before_budget": (row[6]),
                "selected_before_budget": (row[7]),
                "removed_by_budget": row[8],
                "injected": row[9],
            }
            for row in rows
        ]
