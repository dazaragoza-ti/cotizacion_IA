"""
Endpoints de estadísticas de aprendizaje continuo (Sprint 2, Fase 2).

Responde a la pregunta que motivó la tabla `knowledge_stats`
(app/engineering/metrics.py, migración 0001): ¿qué SKU falla más?, ¿cuál
recomiendan más?, ¿cuál reemplazan siempre? Antes esos contadores se
alimentaban pero no se exponían.

Best-effort: si la migración 0001 todavía no está aplicada en Supabase, la
tabla `knowledge_stats` no existe y estos endpoints devuelven 503 con un
mensaje claro en vez de un 500 genérico.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..clients import supabase
from ..engineering.metrics import CAMPOS_VALIDOS

router = APIRouter(prefix="/stats", tags=["stats"])


def _tabla_no_existe(exc: Exception) -> bool:
    texto = str(exc).lower()
    return "does not exist" in texto or "42p01" in texto


@router.get("/sku/{sku}")
def estadisticas_de_sku(sku: str):
    """Contadores acumulados de un SKU puntual (veces_usado/reemplazado/rechazado/recomendado)."""
    try:
        resultado = supabase.table("knowledge_stats").select("*").eq("sku", sku.strip().upper()).limit(1).execute()
    except Exception as exc:  # noqa: BLE001
        if _tabla_no_existe(exc):
            raise HTTPException(
                status_code=503,
                detail="knowledge_stats no existe todavía — falta aplicar backend/db/migrations/0001_knowledge_stats.sql en Supabase.",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not resultado.data:
        raise HTTPException(status_code=404, detail=f"Sin estadísticas registradas para el SKU '{sku}'.")
    return resultado.data[0]


@router.get("/top")
def top_skus(campo: str = "veces_reemplazado", limit: int = 10):
    """
    Ranking de SKUs por un contador de `knowledge_stats`.

    `campo` acepta: veces_usado, veces_reemplazado, veces_rechazado, veces_recomendado.
    Ejemplos: ?campo=veces_reemplazado → qué SKU reemplazan más seguido;
              ?campo=veces_rechazado   → qué SKU falla/rechaza más el usuario;
              ?campo=veces_recomendado → qué SKU recomiendan más como sustituto.
    """
    if campo not in CAMPOS_VALIDOS:
        raise HTTPException(
            status_code=400,
            detail=f"campo inválido: '{campo}'. Válidos: {sorted(CAMPOS_VALIDOS)}.",
        )
    limit = max(1, min(limit, 100))

    try:
        resultado = (
            supabase.table("knowledge_stats")
            .select("*")
            .order(campo, desc=True)
            .limit(limit)
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        if _tabla_no_existe(exc):
            raise HTTPException(
                status_code=503,
                detail="knowledge_stats no existe todavía — falta aplicar backend/db/migrations/0001_knowledge_stats.sql en Supabase.",
            ) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {"campo": campo, "resultados": resultado.data or []}
