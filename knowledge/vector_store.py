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

    def list_by_document_ids(self, document_ids):
        document_ids = set(document_ids)

        return [item for item in self._items if item.chunk.document_id in document_ids]

    def get_by_chunk_id(self, chunk_id):
        for item in self._items:
            if item.chunk.id == chunk_id:
                return item

        return None

    def delete_by_document_id(self, document_id):
        deleted_items = [
            item for item in self._items if item.chunk.document_id == document_id
        ]

        self._items = [
            item for item in self._items if item.chunk.document_id != document_id
        ]

        return deleted_items
