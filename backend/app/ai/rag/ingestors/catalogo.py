from __future__ import annotations

import logging
import time

from app.ai.rag.repository import repository
from app.ai.rag.embeddings import embedding_service
from app.ai.rag.chunkers import catalogo_to_document
from app.ai.rag.checksum import ChecksumService
from app.ai.rag.graph import knowledge_graph

logger = logging.getLogger(__name__)

# Voyage tier gratis: 3 RPM. Agrupar documentos por lote reduce 79 piezas de
# catalogo a ~4 llamadas en vez de 79 -- antes cada pieza hacia su propia
# llamada a embed_text() y el sync completo tumbaba con RateLimitError a la
# primera decena de piezas.
TAMANO_LOTE = 20
# Pausa proactiva entre lotes para no rebasar 3 RPM incluso si ya se
# agruparon los documentos (evita depender solo de los reintentos reactivos).
PAUSA_ENTRE_LOTES_SEG = 21


class CatalogoIngestor:

    TABLA = "catalogo_pm"

    def sync(self):

        logger.info("========== SINCRONIZANDO CATÁLOGO ==========")

        response = repository.catalogo_pm()

        if not response.data:
            logger.warning("No existen piezas.")
            return

        total = len(response.data)
        ignorados = 0

        # --- Paso 1: decidir qué piezas necesitan (re)embedding, sin llamar a Voyage ---
        pendientes = []  # (pieza, pieza_id, documento, checksum, existe)
        for pieza in response.data:
            pieza_id = str(pieza["id"])
            checksum = ChecksumService.calculate(pieza)
            source = repository.get_source(self.TABLA, pieza_id)
            existe = bool(source.data)

            if existe and source.data[0]["checksum"] == checksum:
                ignorados += 1
                continue

            documento = catalogo_to_document(pieza)
            pendientes.append((pieza, pieza_id, documento, checksum, existe))

        nuevos = sum(1 for _, _, _, _, existe in pendientes if not existe)
        actualizados = len(pendientes) - nuevos

        # --- Paso 2: embeddings en lotes (pocas llamadas a Voyage, no una por pieza) ---
        for inicio in range(0, len(pendientes), TAMANO_LOTE):
            lote = pendientes[inicio:inicio + TAMANO_LOTE]
            documentos_lote = [documento for _, _, documento, _, _ in lote]
            embeddings_lote = embedding_service.embed_documents(documentos_lote)

            for (pieza, pieza_id, documento, checksum, existe), embedding in zip(lote, embeddings_lote):
                repository.delete_chunks("catalogo", pieza_id)
                repository.insert_chunk({
                    "tipo": "catalogo",
                    "fuente": "catalogo_pm",
                    "referencia_id": pieza_id,
                    "contenido": documento,
                    "metadata": {
                        "codigo": pieza["codigo"],
                        "descripcion": pieza["descripcion"],
                        "familia": pieza["familia"],
                        "categoria": pieza["categoria"],
                        "frente_mm": pieza["frente_mm"],
                        "fondo_mm": pieza["fondo_mm"],
                        "altura_mm": pieza["altura_mm"],
                        "peralte_mm": pieza["peralte_mm"],
                        "calibre": pieza["calibre"],
                        "carga_kg": pieza["carga_kg"],
                        "precio": pieza["precio"],
                    },
                    "embedding": embedding,
                })

                repository.save_source({
                    "nombre": pieza["codigo"],
                    "tipo": "catalogo",
                    "origen_tabla": self.TABLA,
                    "origen_id": pieza_id,
                    "checksum": checksum,
                    "activo": True,
                })

                knowledge_graph.add_entity(
                    tipo="catalogo",
                    referencia_id=pieza_id,
                    nombre=pieza["codigo"],
                    metadata={
                        "descripcion": pieza["descripcion"],
                        "familia": pieza["familia"],
                        "categoria": pieza["categoria"],
                        "altura": pieza["altura_mm"],
                        "frente": pieza["frente_mm"],
                        "fondo": pieza["fondo_mm"],
                        "calibre": pieza["calibre"],
                        "carga": pieza["carga_kg"],
                    },
                )

                knowledge_graph.add_relation(
                    "catalogo", pieza_id, "pertenece_familia", "familia", pieza["familia"],
                )
                knowledge_graph.add_relation(
                    "catalogo", pieza_id, "pertenece_categoria", "categoria", pieza["categoria"],
                )
                if pieza.get("reglas"):
                    knowledge_graph.add_relation(
                        "catalogo", pieza_id, "tiene_regla", "regla", pieza["codigo"],
                    )
                if pieza.get("carga_kg"):
                    knowledge_graph.add_relation(
                        "catalogo", pieza_id, "soporta", "capacidad", str(pieza["carga_kg"]),
                    )
                if pieza.get("altura_mm"):
                    knowledge_graph.add_relation(
                        "catalogo", pieza_id, "altura", "dimension", str(pieza["altura_mm"]),
                    )
                if pieza.get("frente_mm"):
                    knowledge_graph.add_relation(
                        "catalogo", pieza_id, "frente", "dimension", str(pieza["frente_mm"]),
                    )
                if pieza.get("fondo_mm"):
                    knowledge_graph.add_relation(
                        "catalogo", pieza_id, "fondo", "dimension", str(pieza["fondo_mm"]),
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


catalogo_ingestor = CatalogoIngestor()
