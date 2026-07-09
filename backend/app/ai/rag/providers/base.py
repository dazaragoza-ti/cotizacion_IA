from abc import ABC, abstractmethod
from typing import List


class EmbeddingProvider(ABC):

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        pass

    @abstractmethod
    def embed_documents(
        self,
        docs: List[str]
    ) -> List[List[float]]:
        pass

    def embed_query(self, query: str) -> List[float]:
        """
        Por defecto, igual que embed_text (la mayoría de proveedores usan el
        mismo embedding para documento y consulta). Voyage lo sobreescribe
        porque distingue input_type='document' vs 'query' — mejora la precisión.
        """
        return self.embed_text(query)