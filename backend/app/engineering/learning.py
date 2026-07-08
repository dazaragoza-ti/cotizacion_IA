"""
Planificador de aprendizaje (Sprint 2, Fase 1/3) — lógica PURA.

Traduce un `DiffSku` (qué cambió el usuario en el despiece) en un plan
declarativo de lo que hay que aprender: qué métricas incrementar y qué
relaciones del grafo crear/reforzar. No toca base de datos — por eso es
testeable sin Supabase. El `CorrectionProcessor` es quien EJECUTA este plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.engineering.sku_diff import DiffSku

# Relación de negocio que aprendemos de un reemplazo del usuario.
RELACION_REEMPLAZO = "reemplaza_por"


@dataclass
class PlanAprendizaje:
    # (sku, campo) a incrementar en knowledge_stats
    metricas: list[tuple[str, str]] = field(default_factory=list)
    # (sku_origen, relacion, sku_destino) a crear/reforzar en knowledge_edges
    relaciones: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def vacio(self) -> bool:
        return not self.metricas and not self.relaciones


def planificar_aprendizaje(diff: DiffSku) -> PlanAprendizaje:
    """
    Reglas (v1):
      - Reemplazo viejo→nuevo:
          * viejo += veces_reemplazado, nuevo += veces_recomendado
          * relación `viejo reemplaza_por nuevo`
      - Pieza eliminada (sin sustituto claro): sku += veces_rechazado
      - Pieza agregada (sin origen claro): no genera señal en v1 — no sabemos
        si es "recomendación" o simplemente una pieza nueva del proyecto.
      - Cambios de cantidad del mismo SKU: no generan aprendizaje en v1.
    """
    plan = PlanAprendizaje()

    for viejo, nuevo in diff.reemplazos:
        plan.metricas.append((viejo, "veces_reemplazado"))
        plan.metricas.append((nuevo, "veces_recomendado"))
        plan.relaciones.append((viejo, RELACION_REEMPLAZO, nuevo))

    for sku in diff.eliminados:
        plan.metricas.append((sku, "veces_rechazado"))

    return plan


def metricas_de_uso(proyecto: dict | None) -> list[tuple[str, str]]:
    """
    Al generar/guardar un proyecto, cada SKU de su despiece suma `veces_usado`.
    Pura: devuelve la lista de incrementos; el processor la ejecuta.
    """
    from app.engineering.sku_diff import extraer_piezas

    return [(sku, "veces_usado") for sku in extraer_piezas(proyecto)]
