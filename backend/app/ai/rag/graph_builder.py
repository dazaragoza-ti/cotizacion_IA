from __future__ import annotations

import logging
from collections import defaultdict

from app.ai.rag.graph import knowledge_graph

logger = logging.getLogger(__name__)


class AutomaticGraphBuilder:

    def process_catalog(self, piezas: list[dict]):

        logger.info("Construyendo Knowledge Graph del catálogo...")

        familias = defaultdict(list)
        categorias = defaultdict(list)
        cargas = defaultdict(list)
        alturas = defaultdict(list)
        frentes = defaultdict(list)
        fondos = defaultdict(list)

        ###############################################################
        # Agrupar piezas
        ###############################################################

        for pieza in piezas:

            if pieza.get("familia"):
                familias[pieza["familia"]].append(pieza)

            if pieza.get("categoria"):
                categorias[pieza["categoria"]].append(pieza)

            if pieza.get("carga_kg") is not None:
                cargas[pieza["carga_kg"]].append(pieza)

            if pieza.get("altura_mm") is not None:
                alturas[pieza["altura_mm"]].append(pieza)

            if pieza.get("frente_mm") is not None:
                frentes[pieza["frente_mm"]].append(pieza)

            if pieza.get("fondo_mm") is not None:
                fondos[pieza["fondo_mm"]].append(pieza)

        ###############################################################
        # Procesar grupos
        ###############################################################

        self._build_group(
            familias,
            "misma_familia",
            "Familias"
        )

        self._build_group(
            categorias,
            "misma_categoria",
            "Categorías"
        )

        self._build_group(
            cargas,
            "misma_capacidad",
            "Capacidad"
        )

        self._build_group(
            alturas,
            "misma_altura",
            "Altura"
        )

        self._build_group(
            frentes,
            "mismo_frente",
            "Frente"
        )

        self._build_group(
            fondos,
            "mismo_fondo",
            "Fondo"
        )

        logger.info("Knowledge Graph generado correctamente.")

    ##################################################################

    def _build_group(
        self,
        grupos,
        relation,
        nombre
    ):

        logger.info(f"Procesando grupo {nombre}")

        for valor, elementos in grupos.items():

            if len(elementos) <= 1:
                continue

            ids = [str(x["id"]) for x in elementos]

            for origen in ids:

                for destino in ids:

                    if origen == destino:
                        continue

                    try:

                        knowledge_graph.add_relation(

                            from_tipo="catalogo",

                            from_id=origen,

                            relation=relation,

                            to_tipo="catalogo",

                            to_id=destino,

                            metadata={

                                "grupo": nombre,

                                "valor": valor

                            },

                            confidence=1.0,

                            origen="automatic_builder",

                            validada=True,

                        )

                    except Exception as e:

                        logger.exception(e)


automatic_graph_builder = AutomaticGraphBuilder()