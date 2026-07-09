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

    def upsert_relation(
        self,
        from_tipo: str,
        from_id: str,
        relation: str,
        to_tipo: str,
        to_id: str,
        *,
        correccion_id: int | None = None,
        origen: str = "correccion",
        umbral_confidence: int = 30,
        umbral_promocion: int = 50,
    ) -> dict | None:
        """Crea o refuerza una arista de forma atómica vía el RPC `reforzar_relacion`
        (migración 0003), que incrementa `ocurrencias` y recalcula `confidence`/
        `validada` en una sola sentencia — sin el read-then-write racy que tenía
        el select+update anterior. Devuelve la fila resultante de knowledge_edges.
        """
        resultado = repository.db.rpc(
            "reforzar_relacion",
            {
                "p_from_tipo": from_tipo,
                "p_from_id": from_id,
                "p_relation": relation,
                "p_to_tipo": to_tipo,
                "p_to_id": to_id,
                "p_correccion_id": correccion_id,
                "p_origen": origen,
                "p_umbral_confidence": umbral_confidence,
                "p_umbral_promocion": umbral_promocion,
            },
        ).execute()

        data = resultado.data
        if isinstance(data, list):
            return data[0] if data else None
        return data

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

    def relaciones_relevantes(
        self, tipo: str, referencia_id: str, *, min_confidence: float = 0.5
    ) -> list[dict]:
        """Relaciones salientes de una entidad, filtradas a las que ya acumularon
        suficiente confidence como para mostrárselas a Claude, ordenadas de
        mayor a menor. Usado por el Context Builder para cerrar el bucle de
        lectura del grafo (Sprint 2, Fase 3)."""
        try:
            filas = self.get_relations(tipo, referencia_id).data or []
        except Exception:
            return []
        relevantes = [f for f in filas if (f.get("confidence") or 0) >= min_confidence]
        return sorted(relevantes, key=lambda f: f.get("confidence") or 0, reverse=True)


knowledge_graph = KnowledgeGraph()
