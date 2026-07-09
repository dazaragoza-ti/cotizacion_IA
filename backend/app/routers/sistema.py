"""Endpoints de sistema: health check y configuración pública de Supabase."""
import os
from fastapi import APIRouter, HTTPException

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