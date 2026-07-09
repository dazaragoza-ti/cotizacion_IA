import logging
import os
import time
from typing import List

import voyageai
from voyageai.error import (
    APIConnectionError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    Timeout,
    TryAgain,
)

from app.ai.rag.providers.base import EmbeddingProvider

log = logging.getLogger("rag.voyage_provider")

MAX_REINTENTOS = 3
REINTENTABLES = (
    APIConnectionError,
    RateLimitError,
    ServerError,
    ServiceUnavailableError,
    Timeout,
    TryAgain,
)


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

    def _embed_con_reintentos(self, textos: List[str], input_type: str):
        """Reintenta con backoff exponencial ante rate-limits/errores transitorios
        del lado de Voyage — antes una sola llamada fallida tumbaba todo /rag/sync."""
        ultimo_error: Exception | None = None
        for intento in range(1, MAX_REINTENTOS + 1):
            try:
                return self.client.embed(textos, model=self.MODEL, input_type=input_type)
            except REINTENTABLES as e:
                ultimo_error = e
                log.warning(
                    "Voyage embed reintento %d/%d tras error transitorio: %s",
                    intento, MAX_REINTENTOS, type(e).__name__,
                )
                if intento < MAX_REINTENTOS:
                    time.sleep(2 * intento)
        raise ultimo_error  # se agotaron los reintentos

    def embed_text(self, text: str) -> List[float]:
        resultado = self._embed_con_reintentos([text], "document")
        return resultado.embeddings[0]

    def embed_documents(self, docs: List[str]) -> List[List[float]]:
        resultado = self._embed_con_reintentos(docs, "document")
        return resultado.embeddings

    def embed_query(self, query: str) -> List[float]:
        resultado = self._embed_con_reintentos([query], "query")
        return resultado.embeddings[0]
