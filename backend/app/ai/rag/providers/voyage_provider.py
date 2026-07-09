import os
from typing import List

import voyageai

from app.ai.rag.providers.base import EmbeddingProvider


class VoyageEmbeddingProvider(EmbeddingProvider):
    """
    Voyage AI es el partner de embeddings recomendado por Anthropic. Requiere
    VOYAGE_API_KEY en el .env y el paquete `voyageai` (pip install voyageai).

    ⚠️ Dimensión de salida: voyage-3.5 devuelve 1024 dimensiones por defecto
    (configurable a 256/512/1024/2048 con output_dimension). Si tu columna
    `knowledge_chunks.embedding` en Supabase se creó como vector(1536) para
    calzar con OpenAI, usa output_dimension=1536 aquí O cambia la columna —
    ambos lados deben coincidir exactamente o el insert falla.
    """

    MODEL = "voyage-3.5"

    def __init__(self):
        api_key = os.getenv("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Falta VOYAGE_API_KEY en el .env — necesaria para el proveedor "
                "de embeddings 'voyage' (EMBEDDING_PROVIDER=voyage en config.py)."
            )
        self.client = voyageai.Client(api_key=api_key)

    def embed_text(self, text: str) -> List[float]:
        resultado = self.client.embed([text], model=self.MODEL, input_type="document")
        return resultado.embeddings[0]

    def embed_documents(self, docs: List[str]) -> List[List[float]]:
        resultado = self.client.embed(docs, model=self.MODEL, input_type="document")
        return resultado.embeddings

    def embed_query(self, query: str) -> List[float]:
        resultado = self.client.embed([query], model=self.MODEL, input_type="query")
        return resultado.embeddings[0]