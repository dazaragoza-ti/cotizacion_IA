from __future__ import annotations

import logging
from typing import Any

from app.clients import supabase

logger = logging.getLogger(__name__)


class KnowledgeRepository:

    def __init__(self):

        self.db = supabase

    ####################################################
    # KNOWLEDGE CHUNKS
    ####################################################

    def insert_chunk(
        self,
        data: dict[str, Any]
    ):

        return (

            self.db

            .table("knowledge_chunks")

            .insert(data)

            .execute()

        )

    def delete_chunks(
        self,
        tipo: str,
        referencia_id: str
    ):

        return (

            self.db

            .table("knowledge_chunks")

            .delete()

            .eq("tipo", tipo)

            .eq("referencia_id", referencia_id)

            .execute()

        )

    def search(

        self,

        embedding,

        top_k=8,

        tipo=None

    ):

        return (

            self.db.rpc(

                "match_knowledge",

                {

                    "query_embedding": embedding,

                    "match_count": top_k,

                    "filter_tipo": tipo,

                },

            )

            .execute()

        )

    ####################################################
    # KNOWLEDGE SOURCES
    ####################################################

    def get_source(

        self,

        tabla: str,

        origen_id: str,

    ):

        return (

            self.db

            .table("knowledge_sources")

            .select("*")

            .eq("origen_tabla", tabla)

            .eq("origen_id", origen_id)

            .limit(1)

            .execute()

        )

    def save_source(

        self,

        data

    ):

        return (

            self.db

            .table("knowledge_sources")

            .upsert(

                data,

                on_conflict="origen_tabla,origen_id"

            )

            .execute()

        )

    ####################################################
    # CATALOGO
    ####################################################

    def catalogo_pm(self):

        return (

            self.db

            .table("catalogo_pm")

            .select("*")

            .execute()

        )

    ####################################################
    # REGLAS
    ####################################################

    def reglas(self):

        return (

            self.db

            .table("reglas_armado")

            .select("*")

            .eq("activa", True)

            .execute()

        )

    ####################################################
    # CORRECCIONES
    ####################################################

    def correcciones(self):

        return (

            self.db

            .table("correcciones_armado")

            .select("*")

            .execute()

        )


repository = KnowledgeRepository()