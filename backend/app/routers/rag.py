"""
Endpoints del sistema RAG: disparar la sincronización (indexar catálogo y
correcciones al vector store) y probar búsquedas semánticas manualmente.

La indexación NO es automática en tiempo real todavía — cuando se registra
una corrección nueva (o cambia un precio del catálogo), hay que llamar a
POST /rag/sync para que se vuelva buscable. Es intencional: evita
recalcular embeddings (que cuestan dinero) en cada mensaje de Telegram.
"""
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..ai.rag.sync import knowledge_sync
from ..ai.rag.vector_store import vector_store

log = logging.getLogger("rag_router")
router = APIRouter(prefix="/rag", tags=["rag"])


def _sync_en_segundo_plano() -> None:
    try:
        knowledge_sync.sync_all()
        log.info("rag/sync (background) completado")
    except Exception:
        log.exception("rag/sync (background) fallo")


@router.post("/sync")
def sincronizar_rag(background_tasks: BackgroundTasks):
    """
    Dispara la reindexacion de catalogo (catalogo_pm) y correcciones
    (correcciones_armado) en segundo plano y responde de inmediato.

    Antes esto corria de forma sincrona: con el batching + pausa de 21s entre
    lotes (para no pegarle al rate-limit de Voyage), una sync completa puede
    tardar mas de un minuto -- el cliente (Flutter, connectTimeout de 15s)
    agotaba el timeout y reintentaba, disparando sincronizaciones nuevas
    encima de la que ya estaba corriendo. Con BackgroundTasks el request
    responde al instante y la sincronizacion sigue su curso del lado del
    servidor sin que el cliente tenga que esperarla.
    """
    background_tasks.add_task(_sync_en_segundo_plano)
    return {"status": "started", "mensaje": "Sincronizacion iniciada en segundo plano."}


@router.get("/search")
def buscar_rag(q: str, top_k: int = 5, tipo: str | None = None):
    """Prueba manual: busca los chunks más parecidos semánticamente a `q`."""
    try:
        resultados = vector_store.search(q, top_k=top_k, tipo=tipo)
        return {"query": q, "resultados": resultados}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
