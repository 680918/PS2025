from knowledge.chunker import chunk_document
from knowledge.document_store import DocumentStore
from knowledge.embedding_indexer import (
    index_chunks,
)
from knowledge.loader import load_document
from knowledge.retriever import retrieve_chunks
from knowledge.store import KnowledgeStore
from knowledge.vector_retriever import (
    retrieve_from_vector_store,
)
from knowledge.vector_store import VectorStore


class KnowledgeService:
    def __init__(
        self,
        store=None,
        embedding_provider=None,
        vector_store=None,
        document_store=None,
    ):
        self.store = store or KnowledgeStore()
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store or VectorStore()
        self.document_store = document_store or DocumentStore()

    def add_document(
        self,
        file_path,
        chunk_size=500,
        overlap=0,
    ):
        document = load_document(file_path)

        self.document_store.add(document)

        chunks = chunk_document(
            document,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        self.store.add_many(chunks)

        if self.embedding_provider is not None:
            index_chunks(
                chunks,
                self.embedding_provider,
                self.vector_store,
            )

        return document, chunks

    def search(
        self,
        query,
        top_k=3,
        document_ids=None,
    ):
        if self.embedding_provider is not None:
            return retrieve_from_vector_store(
                query,
                self.vector_store,
                self.embedding_provider,
                top_k=top_k,
                document_ids=document_ids,
            )

        return retrieve_chunks(
            query,
            self.store,
            top_k=top_k,
            document_ids=document_ids,
        )

    def list_chunks(self):
        return self.store.list_all()

    def list_documents(self):
        return self.document_store.list_all()

    def get_document(self, document_id):
        return self.document_store.get_by_id(document_id)

    def delete_document(self, document_id):
        document = self.document_store.delete_by_id(document_id)

        if document is None:
            return None

        self.store.delete_by_document_id(document_id)
        self.vector_store.delete_by_document_id(document_id)

        return document

    def update_document(
        self,
        document_id,
        file_path,
        chunk_size=500,
        overlap=0,
    ):
        existing_document = self.document_store.get_by_id(document_id)

        if existing_document is None:
            return None

        loaded_document = load_document(file_path)

        updated_document = type(existing_document)(
            id=existing_document.id,
            title=loaded_document.title,
            content=loaded_document.content,
            source=loaded_document.source,
            created_at=existing_document.created_at,
        )

        new_chunks = chunk_document(
            updated_document,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        prepared_vectors = []

        if self.embedding_provider is not None:
            temporary_vector_store = VectorStore()

            index_chunks(
                new_chunks,
                self.embedding_provider,
                temporary_vector_store,
            )

            prepared_vectors = temporary_vector_store.list_all()

        self.store.delete_by_document_id(document_id)
        self.vector_store.delete_by_document_id(document_id)

        self.document_store.replace(updated_document)
        self.store.add_many(new_chunks)

        if prepared_vectors:
            self.vector_store.add_many(prepared_vectors)

        return updated_document, new_chunks
