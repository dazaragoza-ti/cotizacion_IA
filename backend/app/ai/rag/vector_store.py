"""
Vector store — fachada de alto nivel sobre knowledge_chunks (pgvector).

`repository.py` expone acceso crudo a las tablas (insert/delete/rpc);
este módulo es la API que deberían usar los ingestors y quien necesite
guardar o buscar contenido sin preocuparse por el detalle de Supabase.
"""
from __future__ import annotations

import logging
from typing import Any

from app.ai.rag.repository import repository
from app.ai.rag.embeddings import embedding_service
from app.ai.tracing import traceable

logger = logging.getLogger(__name__)


class VectorStore:
    def upsert(
        self,
        tipo: str,
        fuente: str,
        referencia_id: str,
        contenido: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Calcula el embedding de `contenido` y lo guarda, reemplazando cualquier chunk previo de esa referencia."""
        embedding = embedding_service.embed_text(contenido)

        repository.delete_chunks(tipo, referencia_id)
        repository.insert_chunk({
            "tipo": tipo,
            "fuente": fuente,
            "referencia_id": referencia_id,
            "contenido": contenido,
            "metadata": metadata or {},
            "embedding": embedding,
        })

    @traceable(name="rag.search", run_type="retriever")
    def search(self, query: str, top_k: int = 8, tipo: str | None = None) -> list[dict]:
        """Busca los chunks más parecidos semánticamente a `query` (usa el RPC
        match_knowledge en Supabase). Trazado como retriever (Sprint 2, Fase 5):
        @traceable captura automáticamente query/top_k/tipo como inputs y la
        lista de chunks (con su score e id) como outputs de la traza."""
        embedding = embedding_service.embed_query(query)
        resultado = repository.search(embedding, top_k=top_k, tipo=tipo)
        return resultado.data or []

    def delete(self, tipo: str, referencia_id: str) -> None:
        repository.delete_chunks(tipo, referencia_id)


vector_store = VectorStore()
