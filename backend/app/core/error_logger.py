"""Persiste errores del backend en Supabase (tabla sistema_errores) para que
el modulo "Arquitectura del Sistema" del frontend los muestre sobre el mapa
de componentes. Best-effort: nunca debe tumbar el flujo que lo llama."""
import logging
from ..clients import supabase

log = logging.getLogger("error_logger")

# Debe reflejar los ids de nodo usados en el frontend
# (frontend/.../features/arquitectura/domain/nodo_arquitectura.dart).
COMPONENTES_VALIDOS = {
    "fastapi", "claude", "rag", "graph", "engineering",
    "generadores", "supabase", "promotion", "context_builder", "qa_visual",
}


def inferir_componente(path: str) -> str:
    """Mapea la ruta del endpoint que fallo a un nodo del mapa de arquitectura."""
    if path.startswith("/rag"):
        return "rag"
    if path.startswith(("/correcciones", "/stats")):
        return "graph"
    if path.startswith(("/catalogo", "/storage")):
        return "supabase"
    if path.startswith("/disenos"):
        return "fastapi"
    return "fastapi"


def registrar_error(componente: str, mensaje: str, endpoint: str | None = None) -> None:
    try:
        supabase.table("sistema_errores").insert({
            "componente": componente if componente in COMPONENTES_VALIDOS else "fastapi",
            "mensaje": mensaje[:2000],
            "endpoint": endpoint,
        }).execute()
    except Exception:
        log.exception("No se pudo registrar el error en sistema_errores (componente=%s)", componente)
