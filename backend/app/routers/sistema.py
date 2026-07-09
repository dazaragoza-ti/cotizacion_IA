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