from typing import List

from app.rag.providers.base import EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):

    def embed_text(self, text: str) -> List[float]:
        raise NotImplementedError()

    def embed_documents(
        self,
        docs: List[str]
    ) -> List[List[float]]:
        raise NotImplementedError()