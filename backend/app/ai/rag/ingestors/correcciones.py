from __future__ import annotations

import logging

from app.ai.rag.repository import repository
from app.ai.rag.embeddings import embedding_service
from app.ai.rag.chunkers import correccion_to_document
from app.ai.rag.checksum import ChecksumService
from app.ai.rag.graph import knowledge_graph

logger = logging.getLogger(__name__)


class CorreccionesIngestor:

    TABLA = "correcciones_armado"

    def sync(self):

        logger.info("========== SINCRONIZANDO CORRECCIONES ==========")

        response = repository.correcciones()

        if not response.data:
            logger.warning("No existen correcciones.")
            return

        nuevos = 0
        actualizados = 0
        ignorados = 0
        total = len(response.data)

        for correccion in response.data:

            correccion_id = str(correccion["id"])
            checksum = ChecksumService.calculate(correccion)

            source = repository.get_source(self.TABLA, correccion_id)
            existe = False

            if source.data:
                existe = True
                if source.data[0]["checksum"] == checksum:
                    ignorados += 1
                    continue

            documento = correccion_to_document(correccion)
            embedding = embedding_service.embed_text(documento)

            repository.delete_chunks("correccion", correccion_id)
            repository.insert_chunk({
                "tipo": "correccion",
                "fuente": "correcciones_armado",
                "referencia_id": correccion_id,
                "contenido": documento,
                "metadata": {
                    "tipo_rack": correccion.get("tipo_rack"),
                    "pieza_afectada": correccion.get("pieza_afectada"),
                    "proyecto_clave": correccion.get("proyecto_clave"),
                    "veces_repetida": correccion.get("veces_repetida"),
                    "origen": correccion.get("origen"),
                },
                "embedding": embedding,
            })

            repository.save_source({
                "nombre": f"correccion_{correccion_id}",
                "tipo": "correccion",
                "origen_tabla": self.TABLA,
                "origen_id": correccion_id,
                "checksum": checksum,
                "activo": True,
            })

            # Relación al Knowledge Graph: esta corrección pertenece a un proyecto/tipo de rack.
            knowledge_graph.add_entity(
                tipo="correccion",
                referencia_id=correccion_id,
                nombre=correccion.get("descripcion_error", "")[:80],
                metadata={
                    "tipo_rack": correccion.get("tipo_rack"),
                    "origen": correccion.get("origen"),
                    "veces_repetida": correccion.get("veces_repetida"),
                },
            )
            if correccion.get("tipo_rack"):
                knowledge_graph.add_relation(
                    "correccion", correccion_id,
                    "aplica_a_tipo", "tipo_rack", correccion["tipo_rack"],
                )
            if correccion.get("proyecto_clave"):
                knowledge_graph.add_relation(
                    "correccion", correccion_id,
                    "corrige_proyecto", "proyecto", correccion["proyecto_clave"],
                )

            if existe:
                actualizados += 1
            else:
                nuevos += 1

        logger.info("===================================")
        logger.info(f"Total           : {total}")
        logger.info(f"Nuevos          : {nuevos}")
        logger.info(f"Actualizados    : {actualizados}")
        logger.info(f"Sin cambios     : {ignorados}")
        logger.info("===================================")


correcciones_ingestor = CorreccionesIngestor()
