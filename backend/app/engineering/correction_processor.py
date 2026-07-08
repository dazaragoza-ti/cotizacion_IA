"""
CorrectionProcessor (Sprint 2, Fase 1) — punto ÚNICO de entrada para procesar
una corrección. Antes, guardar una corrección era solo eso: escribir en
`correcciones_armado` (+ indexar embeddings en vivo). Ahora una corrección
alimenta todo el ecosistema:

    guardar corrección
        ↓ (embeddings/chunk — ya lo hace registrar_correccion internamente)
    diff de SKUs           (app/engineering/sku_diff.py)
        ↓
    plan de aprendizaje    (app/engineering/learning.py)
        ↓
    métricas por SKU       (app/engineering/metrics.py → knowledge_stats)
        ↓
    grafo: reemplaza_por   (knowledge_edges, con confidence reforzada)
        ↓
    promoción a regla      (Fase 4 — parcial: marca `validada` al llegar al umbral)

Cada paso es best-effort: si uno falla (migración sin aplicar, Supabase caído),
se loguea y el resto continúa; nunca rompe la respuesta al cliente.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai.rag.graph import knowledge_graph
from app.ai.rag.repository import repository
from app.engineering import metrics
from app.engineering.learning import (
    metricas_de_uso,
    planificar_aprendizaje,
    PlanAprendizaje,
)
from app.engineering.sku_diff import diff_skus, DiffSku
from app.services import correcciones_pm_service as correcciones

log = logging.getLogger("sprint2.correction_processor")


@dataclass
class ResultadoProceso:
    correccion_id: int | None
    diff: DiffSku | None


class CorrectionProcessor:
    # Ocurrencias necesarias para que una relación llegue a confidence ≈ 0.95.
    UMBRAL_CONFIDENCE = 30
    # Ocurrencias para promover la relación a "regla permanente" (validada=True).
    UMBRAL_PROMOCION = 50

    # ── API pública ─────────────────────────────────────────────────────────
    def process(
        self,
        *,
        session_id: str,
        tg_user_id: int | None,
        tipo: str | None,
        clave: str | None,
        comentario_cliente: str,
        proyecto_antes: dict,
        proyecto_despues: dict,
    ) -> ResultadoProceso:
        """Corrección manual: el cliente ajustó un proyecto ya generado."""
        diff = diff_skus(proyecto_antes, proyecto_despues)

        correccion_id = correcciones.registrar_correccion(
            session_id=session_id, tg_user_id=tg_user_id, tipo=tipo, clave=clave,
            comentario_cliente=comentario_cliente,
            proyecto_antes=proyecto_antes, proyecto_despues=proyecto_despues,
        )

        if diff.hubo_cambio_de_piezas:
            log.info("Corrección %s: %s", correccion_id, diff.resumen())
            self._aprender(planificar_aprendizaje(diff), correccion_id)

        return ResultadoProceso(correccion_id=correccion_id, diff=diff)

    def process_automatica(
        self,
        *,
        session_id: str,
        tg_user_id: int | None,
        tipo: str | None,
        clave: str | None,
        detalle_validacion: str,
        proyecto: dict,
    ) -> ResultadoProceso:
        """Control de calidad: lo que el validador marcó. No hay 'antes', así que
        no hay reemplazos que aprender — solo se guarda (e indexa en vivo)."""
        correccion_id = correcciones.registrar_correccion_automatica(
            session_id=session_id, tg_user_id=tg_user_id, tipo=tipo, clave=clave,
            detalle_validacion=detalle_validacion, proyecto=proyecto,
        )
        return ResultadoProceso(correccion_id=correccion_id, diff=None)

    def registrar_uso(self, proyecto: dict | None) -> None:
        """Suma `veces_usado` a cada SKU del despiece de un proyecto generado."""
        try:
            metrics.increment_many(metricas_de_uso(proyecto))
        except Exception as e:  # noqa: BLE001
            log.warning("registrar_uso falló: %s", e)

    # ── Interno ─────────────────────────────────────────────────────────────
    def _aprender(self, plan: PlanAprendizaje, correccion_id: int | None) -> None:
        try:
            metrics.increment_many(plan.metricas)
        except Exception as e:  # noqa: BLE001
            log.warning("increment de métricas falló: %s", e)

        for origen, relacion, destino in plan.relaciones:
            try:
                self._reforzar_relacion(origen, relacion, destino, correccion_id)
            except Exception as e:  # noqa: BLE001
                log.warning("no se pudo reforzar %s -%s-> %s: %s", origen, relacion, destino, e)

    def _confidence(self, ocurrencias: int) -> float:
        return min(0.95, ocurrencias / self.UMBRAL_CONFIDENCE)

    def _reforzar_relacion(
        self, origen: str, relacion: str, destino: str, correccion_id: int | None
    ) -> None:
        """Crea o refuerza una arista SKU→SKU en knowledge_edges.

        Hoy add_relation() hace INSERT siempre, así que buscamos la arista
        existente y la actualizamos (select+update). La migración 0002 añade el
        índice único que permitirá hacer esto atómico vía upsert más adelante.
        """
        knowledge_graph.add_entity("sku", origen, origen)
        knowledge_graph.add_entity("sku", destino, destino)

        existentes = (knowledge_graph.get_relations("sku", origen).data or [])
        match = next(
            (e for e in existentes
             if e.get("relation") == relacion and e.get("to_id") == destino),
            None,
        )

        if match:
            meta = dict(match.get("metadata") or {})
            ocurrencias = int(meta.get("ocurrencias", 1)) + 1
            meta.update(ocurrencias=ocurrencias, ultima_correccion_id=correccion_id)
            repository.db.table("knowledge_edges").update({
                "metadata": meta,
                "confidence": self._confidence(ocurrencias),
                "validada": ocurrencias >= self.UMBRAL_PROMOCION,
            }).eq("id", match["id"]).execute()
        else:
            knowledge_graph.add_relation(
                "sku", origen, relacion, "sku", destino,
                metadata={"ocurrencias": 1, "ultima_correccion_id": correccion_id},
                confidence=self._confidence(1),
                origen="correccion",
                validada=False,
            )


correction_processor = CorrectionProcessor()
