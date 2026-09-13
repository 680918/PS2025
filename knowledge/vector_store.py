from knowledge.models import EmbeddedChunk


class VectorStore:
    def __init__(self):
        self._items = []

    def add(self, item: EmbeddedChunk):
        self._items.append(item)
        return item

    def add_many(self, items):
        self._items.extend(items)
        return items

    def list_all(self):
        return list(self._items)

    def get_by_chunk_id(self, chunk_id):
        for item in self._items:
            if item.chunk.id == chunk_id:
                return item

        return None
