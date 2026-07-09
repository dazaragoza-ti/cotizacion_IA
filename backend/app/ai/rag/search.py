from __future__ import annotations

import logging
from typing import List, Optional

from app.clients import supabase
from app.ai.rag.embeddings import embedding_service

logger = logging.getLogger(__name__)


class RagSearch:

    def __init__(self):
        self.client = supabase

    def search(
        self,
        query: str,
        top_k: int = 8,
        tipo: Optional[str] = None,
    ) -> List[dict]:

        embedding = embedding_service.embed_query(query)

        response = self.client.rpc(
            "match_knowledge",
            {
                "query_embedding": embedding,
                "match_count": top_k,
                "filter_tipo": tipo,
            },
        ).execute()

        if response.data is None:
            return []

        return response.data

    def build_context(
        self,
        results: List[dict]
    ) -> str:

        context = []

        for item in results:

            context.append(
                f"""
TIPO: {item.get('tipo')}

FUENTE: {item.get('fuente')}

CONTENIDO:

{item.get('contenido')}
"""
            )

        return "\n\n---------------------------\n\n".join(context)


rag_search = RagSearch()