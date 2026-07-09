"""
PromotionEngine (Sprint 2, Fase 4) — traduce las ocurrencias acumuladas de una
relación del grafo en un estado explícito, y materializa las que llegan a
"permanente" como una fila real en `reglas_armado` (la tabla que el agente de
ensamble y el RAG ya leen — ver reglas_service.py / diseno_service.py), para
que la regla deje de vivir solo dentro del grafo y el sistema la aplique sin
depender de que Claude "redescubra" el patrón cada vez desde el contexto.

Estados (acumulativos, por ocurrencias):
    1  → nueva
    5  → importante
    20 → candidata
    50 → permanente (se materializa en reglas_armado, una sola vez — idempotente)

Best-effort: si `reglas_armado` no acepta el insert (esquema distinto, Supabase
caído), se loguea y no rompe el flujo de la corrección.
"""
from __future__ import annotations

import logging

from app.ai.rag.repository import repository

log = logging.getLogger("sprint2.promotion")

UMBRAL_IMPORTANTE = 5
UMBRAL_CANDIDATA = 20
UMBRAL_PERMANENTE = 50


def estado_de(ocurrencias: int) -> str:
    """Estado puro a partir del contador de ocurrencias — sin I/O, testeable."""
    if ocurrencias >= UMBRAL_PERMANENTE:
        return "permanente"
    if ocurrencias >= UMBRAL_CANDIDATA:
        return "candidata"
    if ocurrencias >= UMBRAL_IMPORTANTE:
        return "importante"
    return "nueva"


class PromotionEngine:
    def procesar(self, relacion: dict | None) -> str | None:
        """Recibe la fila de knowledge_edges ya reforzada (ver
        KnowledgeGraph.upsert_relation) y, si cruzó el umbral de permanente,
        la materializa en reglas_armado. Devuelve el estado actual."""
        if not relacion:
            return None

        metadata = relacion.get("metadata") or {}
        try:
            ocurrencias = int(metadata.get("ocurrencias", 1))
        except (TypeError, ValueError):
            ocurrencias = 1

        estado = estado_de(ocurrencias)
        if estado == "permanente":
            self._materializar(relacion, ocurrencias)
        return estado

    def _materializar(self, relacion: dict, ocurrencias: int) -> None:
        from_id = relacion.get("from_id")
        to_id = relacion.get("to_id")
        relation = relacion.get("relation")
        if not from_id or not to_id or not relation:
            return

        condicion = f"{relation}:codigo={from_id}->to={to_id}"
        tipo_rack = "todos"

        try:
            existente = (
                repository.db.table("reglas_armado")
                .select("id")
                .eq("condicion", condicion)
                .eq("tipo_rack", tipo_rack)
                .limit(1)
                .execute()
            )
            if existente.data:
                return  # ya materializada — idempotente

            repository.db.table("reglas_armado").insert({
                "tipo_rack": tipo_rack,
                "condicion": condicion,
                "descripcion": (
                    f"{from_id} {relation} {to_id} "
                    f"({ocurrencias} correcciones lo confirman, aprendizaje continuo)"
                ),
                "accion": f"aplicar {relation}: {from_id} -> {to_id}",
                "activa": True,
            }).execute()
            log.info(
                "Relación %s -%s-> %s promovida a regla permanente en reglas_armado",
                from_id, relation, to_id,
            )
        except Exception as e:  # noqa: BLE001 — promoción es best-effort
            log.warning("No se pudo materializar regla permanente (%s -%s-> %s): %s",
                        from_id, relation, to_id, e)


promotion_engine = PromotionEngine()
