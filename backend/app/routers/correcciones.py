"""Endpoints de correcciones capturadas del agente (modo rack)."""
from fastapi import APIRouter, HTTPException
from ..clients import supabase

router = APIRouter(prefix="/correcciones", tags=["correcciones"])


@router.get("")
def listar_correcciones(limit: int = 100):
    """
    Lista las correcciones capturadas (se aplican automáticamente en el
    agente en cuanto se registran, sin aprobación humana). Sirve para
    visibilidad/auditoría.
    """
    try:
        result = (
            supabase.table("correcciones_armado")
            .select("*")
            .order("veces_repetida", desc=True)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return {"correcciones": result.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{correccion_id}")
def eliminar_correccion(correccion_id: int):
    """
    Elimina una corrección (ej: fue un caso puntual mal capturado, o una
    instrucción errónea que no debe seguir aplicándose). Como ya no hay
    aprobación humana, esta es la única forma de sacar una corrección
    del contexto del agente.
    """
    try:
        supabase.table("correcciones_armado").delete().eq("id", correccion_id).execute()
        return {"status": "success", "correccion_id": correccion_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
