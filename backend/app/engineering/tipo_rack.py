"""Normalización canónica de `tipo_rack` para `reglas_armado` / correcciones.

Canonical: pesada | ligera | cantilever | entrepiso | todos
"""
from __future__ import annotations

TIPOS_CANONICOS = ("pesada", "ligera", "cantilever", "entrepiso", "todos")


def normalizar_tipo_rack(valor: str | None, *, default: str = "todos") -> str:
    """Mapea especificación / layout.tipo / texto libre al set canónico."""
    t = (valor or "").strip().lower()
    if not t:
        return default if default in TIPOS_CANONICOS else "todos"

    if t in TIPOS_CANONICOS:
        return t

    # Acentos / alias frecuentes
    t_norm = (
        t.replace("cantiléver", "cantilever")
        .replace("mezzanín", "mezzanine")
        .replace("mezanine", "mezzanine")
    )

    if "cantilever" in t_norm:
        return "cantilever"
    if "entrepiso" in t_norm or "mezzanine" in t_norm:
        return "entrepiso"
    if "ligera" in t_norm:
        return "ligera"
    if "pesada" in t_norm:
        return "pesada"
    # "selectivo" sin carga explícita → pesada (default de catálogo PM)
    if "selectivo" in t_norm:
        return "pesada"
    if t_norm == "todos" or "universal" in t_norm:
        return "todos"
    return default if default in TIPOS_CANONICOS else "todos"


def tipo_rack_de_proyecto(proyecto: dict | None, *, default: str = "todos") -> str:
    if not proyecto:
        return default if default in TIPOS_CANONICOS else "todos"
    espec = proyecto.get("especificacion")
    if espec:
        return normalizar_tipo_rack(str(espec), default=default)
    tipo_layout = ((proyecto.get("layout") or {}).get("tipo"))
    if tipo_layout:
        return normalizar_tipo_rack(str(tipo_layout), default=default)
    memoria = ((proyecto.get("memoria") or {}).get("tipo_carga"))
    if memoria:
        return normalizar_tipo_rack(str(memoria), default=default)
    return default if default in TIPOS_CANONICOS else "todos"
