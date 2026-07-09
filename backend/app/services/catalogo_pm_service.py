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

from ..clients import supabase

log = logging.getLogger("pm_rackbot.catalogo_pm")

# app/services/catalogo_pm_service.py -> app/ -> app/ai/knowledge/catalogo_pm.json
_JSON_FALLBACK = Path(__file__).parent.parent / "ai" / "knowledge" / "catalogo_pm.json"


def _aplanar_catalogo_anidado(data: dict) -> list[dict]:
    """
    El JSON local viene anidado por subcategoría (fondo_61/peralte_10_sin_escalon/...),
    igual que como lo mantiene un humano a mano. La tabla `catalogo_pm` de
    Supabase, en cambio, es plana (una fila por pieza). Todo el código
    (Compatibility Engine, Context Builder, evaluación...) espera el formato
    plano — así que convertimos aquí, una sola vez, para que dé igual de
    cuál de las dos fuentes vino el catálogo.
    """
    filas: list[dict] = []

    for subcat, items in (data.get("cabeceras_carga_pesada_gota") or {}).items():
        for it in items:
            filas.append({
                "codigo": it["codigo"], "descripcion": it.get("desc", ""), "familia": "pesada",
                "categoria": "cabecera", "subcategoria": subcat,
                "frente_mm": None, "fondo_mm": it.get("fondo_mm"), "altura_mm": it.get("alto_mm"),
                "peralte_mm": None, "calibre": None, "escalon": None, "carga_kg": None,
                "precio": it.get("precio"), "reglas": None,
            })

    for subcat, items in (data.get("largueros_carga_pesada_gota") or {}).items():
        if subcat.startswith("peralte_10"):
            peralte_mm = 100
        elif subcat.startswith("peralte_12_5"):
            peralte_mm = 125
        elif subcat.startswith("peralte_15"):
            peralte_mm = 150
        else:
            peralte_mm = None
        escalon = "con_escalon" in subcat
        for it in items:
            filas.append({
                "codigo": it["codigo"],
                "descripcion": f"LARGUERO PESADO {it.get('frente_mm')}MM PERALTE {peralte_mm}MM {'CON' if escalon else 'SIN'} ESCALON",
                "familia": "pesada", "categoria": "larguero", "subcategoria": subcat,
                "frente_mm": it.get("frente_mm"), "fondo_mm": None, "altura_mm": None,
                "peralte_mm": peralte_mm, "calibre": None, "escalon": escalon,
                "carga_kg": it.get("carga_par_kg"), "precio": it.get("precio"), "reglas": None,
            })

    categoria_por_grupo = {
        "cargador": "cargador", "grapa_unidora_poste": "grapa", "calza_nivelar": "calza",
        "separador_cabecera_gota": "separador", "separador_cabecera_muro": "separador",
        "defensa": "defensa", "entrepiso_extruido": "entrepiso", "tornilleria_taquetes": "tornilleria",
    }
    for grupo, items in (data.get("accesorios") or {}).items():
        categoria = categoria_por_grupo.get(grupo, grupo)
        for it in items:
            desc = it.get("desc", "")
            calibre = 14 if "CAL 14" in desc.upper() else 18 if "CAL 18" in desc.upper() else 22 if "CAL 22" in desc.upper() else None
            familia = "ligera" if "LIGERA" in desc.upper() else "pesada" if "PESADA" in desc.upper() else "comun"
            filas.append({
                "codigo": it["codigo"], "descripcion": desc, "familia": familia,
                "categoria": categoria, "subcategoria": grupo,
                "frente_mm": None, "fondo_mm": it.get("fondo_mm"), "altura_mm": None,
                "peralte_mm": None, "calibre": calibre, "escalon": None, "carga_kg": None,
                "precio": it.get("precio"), "reglas": None,
            })

    return filas


def consultar_catalogo_pm() -> list[dict]:
    """Trae el catálogo real (piezas + precios) desde Supabase. Fallback: el JSON local (aplanado)."""
    try:
        resultado = supabase.table("catalogo_pm").select("*").execute()
        if resultado.data and len(resultado.data) > 0:
            return resultado.data
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo consultar catalogo_pm en Supabase, usando JSON local: %s", e)

    try:
        data = json.loads(_JSON_FALLBACK.read_text(encoding="utf-8"))
        # Soporta ambos formatos por si algún día se reemplaza el JSON local
        # por uno ya plano (ej. exportado directo de Supabase).
        if isinstance(data, list):
            return data
        return _aplanar_catalogo_anidado(data)
    except Exception as e:  # noqa: BLE001
        log.error("Tampoco se pudo leer el catálogo JSON local (%s): %s", _JSON_FALLBACK, e)
        return []
