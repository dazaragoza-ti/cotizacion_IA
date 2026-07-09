from typing import List

from app.ai.rag.providers import get_provider


class EmbeddingService:

    def __init__(self):
        self._provider = None  # perezoso: se crea hasta el primer uso real

    @property
    def provider(self):
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    def embed_text(
        self,
        text: str
    ) -> List[float]:

        return self.provider.embed_text(text)

    def embed_query(
        self,
        query: str
    ) -> List[float]:

        return self.provider.embed_query(query)

    def embed_documents(
        self,
        docs: List[str]
    ) -> List[List[float]]:

        return self.provider.embed_documents(docs)


embedding_service = EmbeddingService()