"""Reglas de armado y correcciones históricas para el agente de ensamble rápido,
más el último diseño guardado de una sesión (usado para versionar disenos_racks)."""
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


def consultar_reglas_armado(tipo_rack: str = "todos") -> list[dict]:
    """
    Reglas técnicas activas (tabla `reglas_armado`) aplicables a `tipo_rack`.
    "todos" trae únicamente las reglas universales; un tipo específico trae
    esas MÁS las universales, para que nunca falte la base común.
    """
    try:
        query = supabase.table("reglas_armado").select("*").eq("activa", True)
        if tipo_rack and tipo_rack != "todos":
            query = query.in_("tipo_rack", [tipo_rack, "todos"])
        else:
            query = query.eq("tipo_rack", "todos")
        return query.execute().data or []
    except Exception:
        return []


def consultar_correcciones_relevantes(tipo_rack: str = "todos") -> list[dict]:
    """
    Correcciones históricas (tabla `correcciones_armado`) aplicables a
    `tipo_rack`, ordenadas por las que más se repiten primero. Fase 1: filtro
    simple por tipo, sin similitud semántica (eso lo cubre el RAG del
    proyectista PM en `vector_store.search`).
    """
    try:
        query = supabase.table("correcciones_armado").select("*")
        if tipo_rack and tipo_rack != "todos":
            query = query.in_("tipo_rack", [tipo_rack, "todos"])
        else:
            query = query.eq("tipo_rack", "todos")
        return (
            query.order("veces_repetida", desc=True).limit(20).execute().data or []
        )
    except Exception:
        return []
