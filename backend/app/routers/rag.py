"""
Endpoints del sistema RAG: disparar la sincronización (indexar catálogo y
correcciones al vector store) y probar búsquedas semánticas manualmente.

La indexación NO es automática en tiempo real todavía — cuando se registra
una corrección nueva (o cambia un precio del catálogo), hay que llamar a
POST /rag/sync para que se vuelva buscable. Es intencional: evita
recalcular embeddings (que cuestan dinero) en cada mensaje de Telegram.
"""
from fastapi import APIRouter, HTTPException

from ..ai.rag.sync import knowledge_sync
from ..ai.rag.vector_store import vector_store

router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/sync")
def sincronizar_rag():
    """Reindexar catálogo (catalogo_pm) y correcciones (correcciones_armado) al vector store."""
    try:
        knowledge_sync.sync_all()
        return {"status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/search")
def buscar_rag(q: str, top_k: int = 5, tipo: str | None = None):
    """Prueba manual: busca los chunks más parecidos semánticamente a `q`."""
    try:
        resultados = vector_store.search(q, top_k=top_k, tipo=tipo)
        return {"query": q, "resultados": resultados}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
