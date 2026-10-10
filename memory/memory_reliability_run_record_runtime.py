from pathlib import Path

from memory.memory_reliability_run_record_store import (
    SQLiteMemoryReliabilityRunRecordStore,
)


def create_user_memory_reliability_run_record_store(
    database_dir,
    user_id,
):
    database_dir = Path(database_dir)

    reliability_dir = database_dir / "memory_reliability"

    reliability_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    return SQLiteMemoryReliabilityRunRecordStore(reliability_dir / f"{user_id}.db")
