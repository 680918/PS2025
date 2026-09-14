from knowledge.models import KnowledgeDocument


class DocumentStore:
    def __init__(self):
        self._documents = []

    def add(self, document: KnowledgeDocument):
        self._documents.append(document)
        return document

    def list_all(self):
        return list(self._documents)

    def get_by_id(self, document_id):
        for document in self._documents:
            if document.id == document_id:
                return document

        return None

    def delete_by_id(self, document_id):
        for index, document in enumerate(self._documents):
            if document.id == document_id:
                return self._documents.pop(index)

        return None

    def replace(self, document: KnowledgeDocument):
        for index, existing_document in enumerate(self._documents):
            if existing_document.id == document.id:
                self._documents[index] = document
                return document

        return None
