from __future__ import annotations

import logging

from app.ai.rag.repository import repository
from app.ai.rag.embeddings import embedding_service
from app.ai.rag.chunkers import catalogo_to_document
from app.ai.rag.checksum import ChecksumService
from app.ai.rag.graph import knowledge_graph

logger = logging.getLogger(__name__)


class CatalogoIngestor:

    TABLA = "catalogo_pm"

    def sync(self):

        logger.info("========== SINCRONIZANDO CATÁLOGO ==========")

        response = repository.catalogo_pm()

        if not response.data:
            logger.warning("No existen piezas.")
            return

        nuevos = 0
        actualizados = 0
        ignorados = 0

        total = len(response.data)

        for pieza in response.data:

            pieza_id = str(pieza["id"])

            checksum = ChecksumService.calculate(pieza)

            source = repository.get_source(
                self.TABLA,
                pieza_id
            )

            existe = False

            if source.data:

                existe = True

                if source.data[0]["checksum"] == checksum:
                    ignorados += 1
                    continue

            ###################################################
            # Construcción del documento
            ###################################################

            documento = catalogo_to_document(pieza)

            ###################################################
            # Embedding
            ###################################################

            embedding = embedding_service.embed_text(documento)

            ###################################################
            # Eliminar chunks anteriores
            ###################################################

            repository.delete_chunks(
                "catalogo",
                pieza_id
            )

            ###################################################
            # Insertar chunk
            ###################################################

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

                    "precio": pieza["precio"]

                },

                "embedding": embedding

            })

            ###################################################
            # Registrar fuente
            ###################################################

            repository.save_source({

                "nombre": pieza["codigo"],

                "tipo": "catalogo",

                "origen_tabla": self.TABLA,

                "origen_id": pieza_id,

                "checksum": checksum,

                "activo": True

            })

            ###################################################
            # Crear entidad del Knowledge Graph
            ###################################################

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

                    "carga": pieza["carga_kg"]

                }

            )

            ###################################################
            # Relaciones automáticas
            ###################################################

            #
            # Familia
            #

            knowledge_graph.add_relation(

                "catalogo",

                pieza_id,

                "pertenece_familia",

                "familia",

                pieza["familia"]

            )

            #
            # Categoría
            #

            knowledge_graph.add_relation(

                "catalogo",

                pieza_id,

                "pertenece_categoria",

                "categoria",

                pieza["categoria"]

            )

            #
            # Reglas
            #

            if pieza.get("reglas"):

                knowledge_graph.add_relation(

                    "catalogo",

                    pieza_id,

                    "tiene_regla",

                    "regla",

                    pieza["codigo"]

                )

            #
            # Capacidad
            #

            if pieza.get("carga_kg"):

                knowledge_graph.add_relation(

                    "catalogo",

                    pieza_id,

                    "soporta",

                    "capacidad",

                    str(pieza["carga_kg"])

                )

            #
            # Altura
            #

            if pieza.get("altura_mm"):

                knowledge_graph.add_relation(

                    "catalogo",

                    pieza_id,

                    "altura",

                    "dimension",

                    str(pieza["altura_mm"])

                )

            #
            # Frente
            #

            if pieza.get("frente_mm"):

                knowledge_graph.add_relation(

                    "catalogo",

                    pieza_id,

                    "frente",

                    "dimension",

                    str(pieza["frente_mm"])

                )

            #
            # Fondo
            #

            if pieza.get("fondo_mm"):

                knowledge_graph.add_relation(

                    "catalogo",

                    pieza_id,

                    "fondo",

                    "dimension",

                    str(pieza["fondo_mm"])

                )

            ###################################################

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


catalogo_ingestor = CatalogoIngestor()