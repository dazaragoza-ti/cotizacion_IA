"""
MetricsService (Sprint 2, Fase 2) — contadores por SKU en `knowledge_stats`.

Best-effort: si la tabla o el RPC `increment_stat` todavía no existen en
Supabase (migración `0001_knowledge_stats.sql` sin aplicar), loguea una
advertencia y sigue. NUNCA debe romper el flujo de corrección.
"""
from __future__ import annotations

import logging

from ..clients import supabase

log = logging.getLogger("sprint2.metrics")

CAMPOS_VALIDOS = {
    "veces_usado",
    "veces_reemplazado",
    "veces_rechazado",
    "veces_recomendado",
}


def increment(sku: str, campo: str, delta: int = 1) -> None:
    """Incrementa un contador de un SKU de forma atómica (RPC en Postgres)."""
    if not sku or campo not in CAMPOS_VALIDOS:
        return
    try:
        supabase.rpc(
            "increment_stat",
            {"p_sku": sku, "p_campo": campo, "p_delta": delta},
        ).execute()
    except Exception as e:  # noqa: BLE001 — métrica es un "extra", nunca tumba el flujo
        log.warning(
            "increment_stat(%s, %s) falló (¿migración 0001 sin aplicar?): %s",
            sku, campo, e,
        )


def increment_many(pares: list[tuple[str, str]]) -> None:
    """Aplica una lista de incrementos `(sku, campo)`."""
    for sku, campo in pares:
        increment(sku, campo)
