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


def open_user_memory_reliability_run_record_store(
    database_dir,
    user_id,
):
    database_dir = Path(database_dir)

    db_path = database_dir / "memory_reliability" / f"{user_id}.db"

    if not db_path.exists():
        raise FileNotFoundError(
            f"Memory reliability database not found for user_id={user_id}"
        )

    return SQLiteMemoryReliabilityRunRecordStore(db_path)
