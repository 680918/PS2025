from pathlib import Path
from memory.service import MemoryService
from memory.sqlite_store import SQLiteMemoryStore
from memory.migration import (
    ensure_skill_map_migrated,
    ensure_user_profile_migrated,
)


DEFAULT_MEMORY_DB_PATH = Path("data") / "memory.db"


def create_memory_service(db_path=None):
    if db_path is None:
        db_path = DEFAULT_MEMORY_DB_PATH

    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    store = SQLiteMemoryStore(db_path)
    service = MemoryService(store)

    ensure_user_profile_migrated(service)
    ensure_skill_map_migrated(service)

    return service
