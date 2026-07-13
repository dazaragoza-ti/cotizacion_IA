import logging
import threading
from datetime import datetime, timezone

from app.ai.rag.ingestors.catalogo import catalogo_ingestor
from app.ai.rag.ingestors.correcciones import correcciones_ingestor

log = logging.getLogger("rag_sync")


class KnowledgeSync:
    """Trae el estado de la sincronizacion en memoria (en_progreso/ultima_ejecucion/
    ultimo_error) para que el endpoint /rag/sync/status pueda informarlo -- el
    POST /rag/sync corre esto en un BackgroundTask y responde de inmediato, asi
    que sin este estado el frontend no tenia forma de saber cuando de verdad
    termino (podia tardar mas de un minuto por el rate-limit de Voyage)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.en_progreso = False
        self.ultima_ejecucion: datetime | None = None
        self.ultimo_error: str | None = None

    def sync_all(self):
        with self._lock:
            if self.en_progreso:
                log.info("sync_all ya esta corriendo -- se ignora esta invocacion duplicada")
                return
            self.en_progreso = True
            self.ultimo_error = None

        try:
            catalogo_ingestor.sync()
            correcciones_ingestor.sync()

            # siguientes módulos (todavía no implementados)

            # reglas_ingestor.sync()

            # proyectos_ingestor.sync()

            # manuales_ingestor.sync()
        except Exception as e:
            self.ultimo_error = str(e)
            raise
        finally:
            self.en_progreso = False
            self.ultima_ejecucion = datetime.now(timezone.utc)


knowledge_sync = KnowledgeSync()