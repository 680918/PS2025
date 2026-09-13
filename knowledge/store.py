from knowledge.models import KnowledgeChunk


class KnowledgeStore:
    def __init__(self):
        self._chunks = []

    def add(self, chunk: KnowledgeChunk):
        self._chunks.append(chunk)
        return chunk

    def add_many(self, chunks):
        self._chunks.extend(chunks)
        return chunks

    def list_all(self):
        return list(self._chunks)

    def get_by_document_id(self, document_id):
        return [
            chunk
            for chunk in self._chunks
            if chunk.document_id == document_id
        ]

    def get_by_id(self, chunk_id):
        for chunk in self._chunks:
            if chunk.id == chunk_id:
                return chunk

        return None