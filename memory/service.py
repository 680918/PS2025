import logging

from memory.models import MemoryRecord
from memory.policy import MemoryPolicy
from datetime import datetime
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass
class MemoryOperationResult:
    memory: MemoryRecord
    action: str
    reason: str
    memory_type: str
    memory_key: str | None


class MemoryService:
    def __init__(self, store, policy=None):
        self.store = store
        self.policy = policy or MemoryPolicy()

    def remember(
        self,
        memory_type,
        memory_key,
        content,
        importance,
        confidence,
        source,
    ):
        result = self.remember_with_result(
            memory_type=memory_type,
            memory_key=memory_key,
            content=content,
            importance=importance,
            confidence=confidence,
            source=source,
        )

        self._log_result(result)

        return result.memory

    def remember_with_result(
        self,
        memory_type,
        memory_key,
        content,
        importance,
        confidence,
        source,
    ):
        existing = self.store.find_by_key(
            memory_type=memory_type,
            memory_key=memory_key,
        )

        if existing is None:
            memory = MemoryRecord(
                memory_type=memory_type,
                memory_key=memory_key,
                content=content,
                importance=importance,
                confidence=confidence,
                source=source,
            )

            self.store.add(memory)

            return MemoryOperationResult(
                memory=memory,
                action="added",
                reason="new_memory",
                memory_type=memory.memory_type,
                memory_key=memory.memory_key,
            )

        new_updated_at = datetime.now().isoformat()

        decision = self.policy.evaluate(
            existing,
            new_confidence=confidence,
            new_importance=importance,
            new_source=source,
            new_updated_at=new_updated_at,
        )

        if not decision.allowed:
            return MemoryOperationResult(
                memory=existing,
                action="kept",
                reason=decision.reason,
                memory_type=existing.memory_type,
                memory_key=existing.memory_key,
            )

        memory = self.store.update(
            existing.id,
            content=content,
            importance=importance,
            confidence=confidence,
            source=source,
        )

        return MemoryOperationResult(
            memory=memory,
            action="updated",
            reason=decision.reason,
            memory_type=memory.memory_type,
            memory_key=memory.memory_key,
        )

    def _log_result(self, result):
        logger.info(
            "memory_decision action=%s reason=%s memory_type=%s memory_key=%s",
            result.action,
            result.reason,
            result.memory_type,
            result.memory_key,
        )

    def get_context(self):

        memory_types = [
            "profile",
            "skill",
            "learning",
            "project",
            "experience",
        ]

        context = {}

        for memory_type in memory_types:
            memories = self.store.list_by_type(memory_type)

            context[memory_type] = [
                {
                    "id": memory.id,
                    "memory_key": memory.memory_key,
                    "content": memory.content,
                    "importance": memory.importance,
                    "confidence": memory.confidence,
                    "source": memory.source,
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                }
                for memory in memories
            ]

        return context

    def get_by_key(self, memory_type, memory_key):

        return self.store.find_by_key(
            memory_type,
            memory_key,
        )
