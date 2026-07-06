from typing import List

from app.rag.providers import get_provider


class EmbeddingService:

    def __init__(self):

        self.provider = get_provider()

    def embed_text(
        self,
        text: str
    ) -> List[float]:

        return self.provider.embed_text(text)

    def embed_query(
        self,
        query: str
    ) -> List[float]:

        return self.provider.embed_text(query)

    def embed_documents(
        self,
        docs: List[str]
    ) -> List[List[float]]:

        return self.provider.embed_documents(docs)


embedding_service = EmbeddingService()