from datetime import datetime

from memory.models import MemoryRecord


class MemoryStore:
    def __init__(self):
        self._memories = {}

    def add(self, memory: MemoryRecord):
        self._memories[memory.id] = memory

    def get(self, memory_id: str):
        return self._memories.get(memory_id)

    def list_by_type(self, memory_type: str):
        return [
            memory
            for memory in self._memories.values()
            if memory.memory_type == memory_type
        ]

    def find_by_key(self, memory_type: str, memory_key: str):
        for memory in self._memories.values():
            if memory.memory_type == memory_type and memory.memory_key == memory_key:
                return memory

        return None

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

        original_values = {}

        for field, value in changes.items():
            original_values[field] = getattr(memory, field)
            setattr(memory, field, value)

        try:
            memory.validate()
        except ValueError:
            for field, value in original_values.items():
                setattr(memory, field, value)
            raise

        memory.updated_at = datetime.now().isoformat()

        return memory
