"""
Catálogo real del proyectista PM — ahora vive en Supabase (tabla catalogo_pm),
no solo en el archivo knowledge/catalogo_pm.json. Así puedes corregir un
precio o dar de alta un código nuevo desde el SQL editor / table editor de
Supabase, sin tener que redesplegar el backend.

Si la tabla está vacía o la consulta falla, cae al JSON local (el mismo que
ya tenías) para que el bot nunca se quede sin catálogo.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ...clients import supabase

log = logging.getLogger("pm_rackbot.catalogo_pm")

_JSON_FALLBACK = Path(__file__).parent / "knowledge" / "catalogo_pm.json"


def consultar_catalogo_pm() -> list[dict]:
    """Trae el catálogo real (piezas + precios) desde Supabase. Fallback: el JSON local."""
    try:
        resultado = supabase.table("catalogo_pm").select("*").execute()
        if resultado.data and len(resultado.data) > 0:
            return resultado.data
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo consultar catalogo_pm en Supabase, usando JSON local: %s", e)

    try:
        return json.loads(_JSON_FALLBACK.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.error("Tampoco se pudo leer el catálogo JSON local: %s", e)
        return []
