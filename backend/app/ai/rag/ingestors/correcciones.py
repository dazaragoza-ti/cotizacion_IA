from __future__ import annotations

import logging
import time

from app.ai.rag.repository import repository
from app.ai.rag.embeddings import embedding_service
from app.ai.rag.chunkers import correccion_to_document
from app.ai.rag.checksum import ChecksumService
from app.ai.rag.graph import knowledge_graph

logger = logging.getLogger(__name__)

# Mismo motivo que en catalogo.py: agrupar documentos por lote evita hacer una
# llamada a Voyage por cada correccion y disparar RateLimitError con el tier
# gratis (3 RPM).
TAMANO_LOTE = 20
PAUSA_ENTRE_LOTES_SEG = 21


class CorreccionesIngestor:

    TABLA = "correcciones_armado"

    def sync(self):

        logger.info("========== SINCRONIZANDO CORRECCIONES ==========")

        response = repository.correcciones()

        if not response.data:
            logger.warning("No existen correcciones.")
            return

        total = len(response.data)
        ignorados = 0

        # --- Paso 1: decidir que correcciones necesitan (re)embedding, sin llamar a Voyage ---
        pendientes = []  # (correccion, correccion_id, documento, checksum, existe)
        for correccion in response.data:
            correccion_id = str(correccion["id"])
            checksum = ChecksumService.calculate(correccion)
            source = repository.get_source(self.TABLA, correccion_id)
            existe = bool(source.data)

            if existe and source.data[0]["checksum"] == checksum:
                ignorados += 1
                continue

            documento = correccion_to_document(correccion)
            pendientes.append((correccion, correccion_id, documento, checksum, existe))

        nuevos = sum(1 for _, _, _, _, existe in pendientes if not existe)
        actualizados = len(pendientes) - nuevos

        # --- Paso 2: embeddings en lotes ---
        for inicio in range(0, len(pendientes), TAMANO_LOTE):
            lote = pendientes[inicio:inicio + TAMANO_LOTE]
            documentos_lote = [documento for _, _, documento, _, _ in lote]
            embeddings_lote = embedding_service.embed_documents(documentos_lote)

            for (correccion, correccion_id, documento, checksum, existe), embedding in zip(lote, embeddings_lote):
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

            hay_mas_lotes = inicio + TAMANO_LOTE < len(pendientes)
            if hay_mas_lotes:
                time.sleep(PAUSA_ENTRE_LOTES_SEG)

        logger.info("===================================")
        logger.info(f"Total           : {total}")
        logger.info(f"Nuevos          : {nuevos}")
        logger.info(f"Actualizados    : {actualizados}")
        logger.info(f"Sin cambios     : {ignorados}")
        logger.info("===================================")


correcciones_ingestor = CorreccionesIngestor()
