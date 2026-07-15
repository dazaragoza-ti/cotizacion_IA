"""Endpoints de sistema: health check, configuración pública de Supabase y
fallos recientes del backend (para el módulo Arquitectura del Sistema)."""
import os
from fastapi import APIRouter, HTTPException
from ..clients import supabase

router = APIRouter(tags=["sistema"])


@router.get("/")
async def root():
    return {"status": "healthy", "service": "RackBuilder 3D API"}

@router.get("/config/supabase")
async def get_supabase_config():
    """Expone la URL y la anon key de Supabase para que el frontend las tome automáticamente del .env del servidor."""
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_KEY", "")
    if not url or not key:
        raise HTTPException(status_code=500, detail="SUPABASE_URL o SUPABASE_KEY no están configuradas en el .env del servidor.")
    return {"url": url, "key": key}

@router.get("/sistema/errores")
async def listar_errores_sistema(limit: int = 20, solo_activos: bool = True):
    """Fallos recientes registrados por los exception handlers globales
    (ver app/main.py + app/core/error_logger.py)."""
    query = supabase.table("sistema_errores").select("*").order("created_at", desc=True).limit(limit)
    if solo_activos:
        query = query.eq("resuelto", False)
    result = query.execute()
    return {"errores": result.data or []}

@router.post("/sistema/errores/{error_id}/resolver")
async def resolver_error_sistema(error_id: str):
    supabase.table("sistema_errores").update({"resuelto": True}).eq("id", error_id).execute()
    return {"ok": True}

@router.get("/sistema/metricas")
async def metricas_por_nodo():
    """
    Metricas reales por nodo del mapa de Arquitectura del Sistema -- la
    estructura del mapa (nodos/conexiones) sigue siendo estatica (es
    documentacion, no un grafo autodescubierto), pero cada nodo ahora puede
    mostrar un dato real y actual al tocarlo, en vez de solo texto fijo.
    Best-effort por nodo: si una consulta falla, ese nodo simplemente no
    trae metrica en vez de tumbar el resto.
    """
    metricas: dict = {}

    metricas["fastapi"] = {"estado": "activo"}
    metricas["langsmith"] = {"configurado": bool(os.getenv("LANGSMITH_API_KEY"))}

    try:
        supabase.table("catalogo_pm").select("codigo").limit(1).execute()
        metricas["supabase"] = {"estado": "conectado"}
    except Exception:
        metricas["supabase"] = {"estado": "sin conexion"}

    try:
        chunks = supabase.table("knowledge_chunks").select("id").execute()
        metricas["rag"] = {"chunks_indexados": len(chunks.data or [])}
    except Exception:
        metricas["rag"] = {}

    try:
        edges = supabase.table("knowledge_edges").select("id").execute()
        metricas["graph"] = {"relaciones_activas": len(edges.data or [])}
    except Exception:
        metricas["graph"] = {}

    try:
        filas = (
            supabase.table("disenos_racks")
            .select("input_tokens,output_tokens")
            .execute()
        ).data or []
        input_total = sum(f.get("input_tokens") or 0 for f in filas)
        output_total = sum(f.get("output_tokens") or 0 for f in filas)
        costo = input_total / 1_000_000 * 3.00 + output_total / 1_000_000 * 15.00
        metricas["claude"] = {
            "disenos_generados": len(filas),
            "tokens_totales": input_total + output_total,
            "costo_usd": round(costo, 2),
        }
    except Exception:
        metricas["claude"] = {}

    try:
        reglas = supabase.table("reglas_armado").select("id").eq("activa", True).execute()
        metricas["promotion"] = {"reglas_activas": len(reglas.data or [])}
    except Exception:
        metricas["promotion"] = {}

    return {"metricas": metricas}