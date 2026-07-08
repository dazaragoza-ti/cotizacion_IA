"""Utilidades de texto para el bot."""
from __future__ import annotations

import json as _json
import re


def extraer_bloque(texto: str, lang: str) -> tuple[str | None, str]:
    """Separa el primer bloque ```<lang> ...``` del resto del texto.

    Devuelve (contenido_o_None, texto_sin_el_bloque).
    """
    patron = re.compile(r"```" + lang + r"\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    m = patron.search(texto)
    if m:
        contenido = m.group(1).strip()
        resto = (texto[: m.start()] + texto[m.end():]).strip()
        return contenido, resto
    return None, texto


def extraer_html(texto: str) -> tuple[str | None, str]:
    return extraer_bloque(texto, "html")


def extraer_json(texto: str) -> tuple[dict | None, str]:
    """Extrae y parsea el bloque ```json. Devuelve (dict_o_None, resto)."""
    bloque, resto = extraer_bloque(texto, "json")
    if bloque is None:
        return None, resto
    try:
        return _json.loads(bloque), resto
    except Exception:
        return None, resto


def trocear(texto: str, limite: int = 4000) -> list[str]:
    """Parte el texto en trozos que quepan en un mensaje de Telegram (4096 máx)."""
    texto = texto.strip()
    if not texto:
        return ["(sin texto)"]
    return [texto[i : i + limite] for i in range(0, len(texto), limite)]
