from knowledge.chunker import chunk_document
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
    ):
        self.store = store or KnowledgeStore()

        self.embedding_provider = (
            embedding_provider
        )

        self.vector_store = (
            vector_store
            or VectorStore()
        )

    def add_document(
        self,
        file_path,
        chunk_size=500,
        overlap=0,
    ):
        document = load_document(file_path)

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
    ):
        if self.embedding_provider is not None:
            return retrieve_from_vector_store(
                query,
                self.vector_store,
                self.embedding_provider,
                top_k=top_k,
            )

        return retrieve_chunks(
            query,
            self.store,
            top_k=top_k,
        )

    def list_chunks(self):
        return self.store.list_all()