"""Endpoints de consulta del historial de diseños (modo rack)."""
from fastapi import APIRouter, HTTPException
from ..clients import supabase

router = APIRouter(prefix="/disenos", tags=["disenos"])


@router.get("/historial")
def get_historial_disenos(limit: int = 50):
    """Lista todos los diseños con su historial de versiones y comentarios."""
    try:
        result = supabase.table("disenos_racks")             .select("id,created_at,vendedor_id,session_id,solicitud_original,version_actual,historial_comentarios,input_tokens,output_tokens")             .order("created_at", desc=True)             .limit(limit)             .execute()
        return {"disenos": result.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/sesion/{session_id}")
def get_versiones_sesion(session_id: str):
    """Lista todas las versiones de una sesión específica."""
    try:
        result = supabase.table("disenos_racks")             .select("*")             .eq("session_id", session_id)             .order("version_actual", desc=False)             .execute()
        return {"session_id": session_id, "versiones": result.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
