"""
Planificador de aprendizaje (Sprint 2, Fase 1/3) — lógica PURA.

Traduce un `DiffSku` (qué cambió el usuario en el despiece) en un plan
declarativo de lo que hay que aprender: qué métricas incrementar y qué
relaciones del grafo crear/reforzar. No toca base de datos — por eso es
testeable sin Supabase. El `CorrectionProcessor` es quien EJECUTA este plan.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.engineering.sku_diff import DiffSku, familia

# Relación de negocio que aprendemos de un reemplazo del usuario.
RELACION_REEMPLAZO = "reemplaza_por"
# Dos SKUs que convivieron, sin cambios, en un proyecto ya corregido/validado.
RELACION_COMPATIBLE = "compatible_con"
# Un SKU que el usuario quitó mientras el resto del proyecto se mantenía.
RELACION_EVITAR = "evitar_con"

# Tope de relaciones compatible_con/evitar_con por SKU de contexto, para no
# generar O(n²) aristas en proyectos con despieces grandes (v1, conservador:
# solo empareja contra piezas de OTRA familia, que es la señal más limpia —
# dos piezas de la misma familia normalmente son alternativas, no un combo).
MAX_PARES_CONTEXTO = 5


@dataclass
class PlanAprendizaje:
    # (sku, campo) a incrementar en knowledge_stats
    metricas: list[tuple[str, str]] = field(default_factory=list)
    # (sku_origen, relacion, sku_destino) a crear/reforzar en knowledge_edges
    relaciones: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def vacio(self) -> bool:
        return not self.metricas and not self.relaciones


def _contexto_distinta_familia(sku: str, candidatos: list[str]) -> list[str]:
    fam = familia(sku)
    return [c for c in candidatos if familia(c) != fam][:MAX_PARES_CONTEXTO]


def planificar_aprendizaje(diff: DiffSku) -> PlanAprendizaje:
    """
    Reglas (v1):
      - Reemplazo viejo→nuevo:
          * viejo += veces_reemplazado, nuevo += veces_recomendado
          * relación `viejo reemplaza_por nuevo`
          * relación `nuevo compatible_con X` por cada pieza de otra familia
            que se mantuvo sin cambio — el nuevo SKU quedó validado conviviendo
            con el resto del proyecto corregido.
      - Pieza eliminada (sin sustituto claro): sku += veces_rechazado
          * relación `sku evitar_con X` por cada pieza de otra familia que
            seguía presente cuando el usuario decidió quitar `sku` — señal
            débil pero conservadora de que esa combinación no funcionó.
      - Pieza agregada (sin origen claro): no genera señal en v1 — no sabemos
        si es "recomendación" o simplemente una pieza nueva del proyecto.
      - Cambios de cantidad del mismo SKU: no generan aprendizaje en v1.
    """
    plan = PlanAprendizaje()

    for viejo, nuevo in diff.reemplazos:
        plan.metricas.append((viejo, "veces_reemplazado"))
        plan.metricas.append((nuevo, "veces_recomendado"))
        plan.relaciones.append((viejo, RELACION_REEMPLAZO, nuevo))

        for otro in _contexto_distinta_familia(nuevo, diff.sin_cambio):
            plan.relaciones.append((nuevo, RELACION_COMPATIBLE, otro))

    for sku in diff.eliminados:
        plan.metricas.append((sku, "veces_rechazado"))

        for otro in _contexto_distinta_familia(sku, diff.sin_cambio):
            plan.relaciones.append((sku, RELACION_EVITAR, otro))

    return plan


def metricas_de_uso(proyecto: dict | None) -> list[tuple[str, str]]:
    """
    Al generar/guardar un proyecto, cada SKU de su despiece suma `veces_usado`.
    Pura: devuelve la lista de incrementos; el processor la ejecuta.
    """
    from app.engineering.sku_diff import extraer_piezas

    return [(sku, "veces_usado") for sku in extraer_piezas(proyecto)]
