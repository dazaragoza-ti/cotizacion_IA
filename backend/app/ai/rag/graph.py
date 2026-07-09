from __future__ import annotations

from app.ai.rag.repository import repository


class KnowledgeGraph:

    ####################################################
    # ENTIDADES
    ####################################################

    def add_entity(
        self,
        tipo,
        referencia_id,
        nombre,
        metadata=None,
    ):

        repository.db.table(
            "knowledge_entities"
        ).upsert({

            "tipo": tipo,

            "referencia_id": referencia_id,

            "nombre": nombre,

            "metadata": metadata or {}

        }).execute()

    ####################################################
    # RELACIONES
    ####################################################

    def add_relation(

        self,

        from_tipo,

        from_id,

        relation,

        to_tipo,

        to_id,

        metadata=None,

        confidence=1.0,

        origen="system",

        validada=False,

    ):

        repository.db.table(
            "knowledge_edges"
        ).insert({

            "from_tipo": from_tipo,

            "from_id": from_id,

            "relation": relation,

            "to_tipo": to_tipo,

            "to_id": to_id,

            "metadata": metadata or {},

            "confidence": confidence,

            "origen": origen,

            "validada": validada

        }).execute()

    ####################################################

    def get_relations(

        self,

        tipo,

        referencia_id,

    ):

        return (

            repository.db

            .table("knowledge_edges")

            .select("*")

            .eq("from_tipo", tipo)

            .eq("from_id", referencia_id)

            .execute()

        )


knowledge_graph = KnowledgeGraph()