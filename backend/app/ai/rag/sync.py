from app.ai.rag.ingestors.catalogo import catalogo_ingestor
from app.ai.rag.ingestors.correcciones import correcciones_ingestor


class KnowledgeSync:

    def sync_all(self):

        catalogo_ingestor.sync()
        correcciones_ingestor.sync()

        # siguientes módulos (todavía no implementados)

        # reglas_ingestor.sync()

        # proyectos_ingestor.sync()

        # manuales_ingestor.sync()


knowledge_sync = KnowledgeSync()