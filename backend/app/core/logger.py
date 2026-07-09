"""
Configuracion centralizada de logging (Capitulo 3.6 de AI_ENGINEERING_MANUAL.md:
"core/ -> logger.py: configuracion global de logging").

Antes de esto no existia ningun logging.basicConfig() en el proyecto: cada
modulo llama logging.getLogger(__name__) (hay 19 en app/) pero sin un handler
configurado en el logger raiz, el nivel INFO por defecto de Python NO se
muestra (solo WARNING+ via el "handler de ultimo recurso"). En la practica,
la mayoria de los log.info(...) del proyecto (progreso de correcciones,
promociones del grafo, sincronizacion RAG, etc.) nunca llegaban a verse.
"""
from __future__ import annotations

import logging
import os

_CONFIGURADO = False


def configurar_logging() -> None:
    """Configura el logger raiz una sola vez. Llamar al arrancar la app
    (ver app/main.py). Nivel configurable via LOG_LEVEL (INFO por defecto)."""
    global _CONFIGURADO
    if _CONFIGURADO:
        return

    nivel = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, nivel, logging.INFO),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _CONFIGURADO = True
