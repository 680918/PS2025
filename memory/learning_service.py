import json
from dataclasses import asdict

from memory.learning_models import LearningRecord


class LearningMemoryService:
    def __init__(self, memory_service):
        self.memory_service = memory_service

    def save(self, record: LearningRecord):
        content = json.dumps(
            asdict(record),
            ensure_ascii=False,
        )

        return self.memory_service.remember(
            memory_type="learning",
            memory_key=record.id,
            content=content,
            importance=0.8,
            confidence=0.9,
            source=record.source,
        )

    def list_records(self):
        memories = self.memory_service.store.list_by_type("learning")

        records = []

        for memory in memories:
            data = json.loads(memory.content)
            records.append(LearningRecord(**data))

        return records

    def get_history(self, topic=None):
        records = self.list_records()

        if topic is None:
            return records

        return [record for record in records if record.topic == topic]
