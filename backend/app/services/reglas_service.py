"""Último diseño guardado de una sesión (usado para versionar disenos_racks)."""
from ..clients import supabase


def obtener_ultimo_diseno(session_id: str) -> dict | None:
    """
    Recupera la versión más reciente del diseño actual para esta sesión de chat.
    """
    try:
        resultado = supabase.table("disenos_racks").select("*").eq("session_id", session_id).order("version_actual", desc=True).limit(1).execute()
        return resultado.data[0] if resultado.data else None
    except Exception:
        return None
