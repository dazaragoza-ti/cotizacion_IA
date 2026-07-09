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
    grafo: reemplaza_por / evitar_con / compatible_con (knowledge_edges,
           upsert atómico vía RPC reforzar_relacion — migración 0003)
        ↓
    promoción a regla      (app/engineering/promotion.py → reglas_armado)

Cada paso es best-effort: si uno falla (migración sin aplicar, Supabase caído),
se loguea y el resto continúa; nunca rompe la respuesta al cliente.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai.rag.graph import knowledge_graph
from app.engineering import metrics
from app.engineering.learning import (
    metricas_de_uso,
    planificar_aprendizaje,
    PlanAprendizaje,
)
from app.engineering.promotion import promotion_engine
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

    def _reforzar_relacion(
        self, origen: str, relacion: str, destino: str, correccion_id: int | None
    ) -> None:
        """Crea o refuerza una arista SKU→SKU en knowledge_edges de forma atómica
        (RPC reforzar_relacion, migración 0003 — reemplaza el select+update racy
        de antes) y, si cruza el umbral de promoción, la materializa como regla
        permanente vía PromotionEngine."""
        knowledge_graph.add_entity("sku", origen, origen)
        knowledge_graph.add_entity("sku", destino, destino)

        resultado = knowledge_graph.upsert_relation(
            "sku", origen, relacion, "sku", destino,
            correccion_id=correccion_id,
            origen="correccion",
            umbral_confidence=self.UMBRAL_CONFIDENCE,
            umbral_promocion=self.UMBRAL_PROMOCION,
        )
        estado = promotion_engine.procesar(resultado)
        if estado:
            log.info("Relación %s -%s-> %s en estado '%s'", origen, relacion, destino, estado)


correction_processor = CorrectionProcessor()
