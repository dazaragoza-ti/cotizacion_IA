"""
Compatibility Engine — determinista, sin IA.

Responde dos preguntas que Claude NUNCA debería tener que "adivinar":

1. Dado un familia + medidas (frente/fondo/peralte), ¿qué piezas reales del
   catálogo son compatibles? (`piezas_compatibles`)
2. Dado un proyecto ya generado, ¿los códigos que Claude eligió coinciden
   de verdad con las medidas físicas declaradas en el layout, según el
   catálogo real? (`verificar_compatibilidad_proyecto`)

No usa embeddings, no usa el Knowledge Graph, no llama a Claude. Es
exactamente el tipo de módulo que el propio AI_ENGINEERING_MANUAL.md pide en
el Capítulo 6: "La IA nunca debe inventar... una compatibilidad. Toda
decisión técnica debe provenir del Engineering Engine."
"""
from __future__ import annotations

import logging

log = logging.getLogger("pm_rackbot.compatibility")


def _sku_de(pieza: dict) -> str | None:
    return pieza.get("codigo") or pieza.get("codigo_sku")


def inferir_familia(
    descripcion: str | None = None,
    proyecto_anterior: dict | None = None,
) -> str | None:
    """Infiere `pesada` / `ligera` desde el proyecto previo o el mensaje.

    Devuelve None si hay ambigüedad (cantilever genérico, sin keywords, etc.).
    """
    if proyecto_anterior:
        espec = (proyecto_anterior.get("especificacion") or "").lower()
        if "pesada" in espec:
            return "pesada"
        if "ligera" in espec:
            return "ligera"

    texto = (descripcion or "").lower()
    if "carga pesada" in texto or "pesada gota" in texto or (
        "pesada" in texto and "ligera" not in texto
    ):
        return "pesada"
    if "carga ligera" in texto or "ligera gota" in texto or (
        "ligera" in texto and "pesada" not in texto
    ):
        return "ligera"
    return None


def filtrar_catalogo_por_familia(
    catalogo_pm: list[dict],
    familia: str | None,
) -> tuple[list[dict], str]:
    """Subset del catálogo para el system prompt del proyectista.

    - Con familia clara: piezas de esa familia + `comun`.
    - Sin familia (ambigüedad): catálogo completo + log (fallback seguro).

    Devuelve `(filas, modo)` donde modo es `familia=<x>` o `fallback_completo`.
    """
    if not catalogo_pm:
        return [], "vacio"

    if familia not in ("pesada", "ligera"):
        log.info(
            "Catálogo sin filtro de familia (ambigüedad) — se envía completo (%d piezas)",
            len(catalogo_pm),
        )
        return list(catalogo_pm), "fallback_completo"

    grupos = piezas_compatibles(catalogo_pm, familia)
    filtrado = grupos["cabeceras"] + grupos["largueros"] + grupos["comunes"]
    # Deduplicar por código por si un accesorio cae en comunes dos veces.
    vistos: set[str] = set()
    unicos: list[dict] = []
    for p in filtrado:
        sku = _sku_de(p) or id(p)
        key = str(sku)
        if key in vistos:
            continue
        vistos.add(key)
        unicos.append(p)

    log.info(
        "Catálogo filtrado familia=%s: %d/%d piezas",
        familia, len(unicos), len(catalogo_pm),
    )
    return unicos, f"familia={familia}"


def piezas_compatibles(
    catalogo_pm: list[dict],
    familia: str,
    frente_mm: int | None = None,
    fondo_mm: int | None = None,
    peralte_mm: int | None = None,
) -> dict[str, list[dict]]:
    """
    Filtra el catálogo real a SOLO las piezas físicamente compatibles con la
    familia (pesada/ligera) y las medidas dadas. Piezas 'comun' (tornillería,
    taquetes, calzas...) siempre se incluyen porque no dependen de medida.

    Uso típico: en vez de mandarle a Claude las 79 piezas completas, dale
    solo las 8-12 que de verdad aplican al caso — esto es la base del
    Context Builder que sigue después de este módulo.
    """
    cabeceras, largueros, comunes = [], [], []

    for p in catalogo_pm or []:
        fam = p.get("familia")
        cat = p.get("categoria")

        if fam == "comun":
            comunes.append(p)
            continue

        if fam != familia:
            continue

        if cat == "cabecera":
            if fondo_mm is None or p.get("fondo_mm") in (None, fondo_mm):
                cabeceras.append(p)
        elif cat == "larguero":
            frente_ok = frente_mm is None or p.get("frente_mm") in (None, frente_mm)
            peralte_ok = peralte_mm is None or p.get("peralte_mm") in (None, peralte_mm)
            if frente_ok and peralte_ok:
                largueros.append(p)
        else:
            # accesorios de familia específica (cargadores, tensores, entrepaños...)
            comunes.append(p)

    return {"cabeceras": cabeceras, "largueros": largueros, "comunes": comunes}


def es_compatible(codigo_a: str, codigo_b: str, catalogo_pm: list[dict]) -> tuple[bool, str]:
    """
    Compatibilidad puntual entre dos códigos específicos (ej. una cabecera y
    un larguero). No usa heurísticas — compara familia y, si aplica, medidas.
    """
    indice = {_sku_de(p): p for p in catalogo_pm if _sku_de(p)}
    a, b = indice.get(codigo_a), indice.get(codigo_b)

    if not a or not b:
        faltante = codigo_a if not a else codigo_b
        return False, f"'{faltante}' no existe en el catálogo."

    fam_a, fam_b = a.get("familia"), b.get("familia")
    if fam_a not in (fam_b, "comun") and fam_b not in (fam_a, "comun"):
        return False, f"Familias distintas: {codigo_a}={fam_a} vs {codigo_b}={fam_b} (pesada y ligera no son compatibles — postes de 73mm vs 38mm)."

    # Si una es cabecera y la otra larguero, el fondo/frente deben cuadrar con el layout,
    # pero eso ya lo valida verificar_compatibilidad_proyecto (necesita el layout completo).
    return True, "Compatible."


def verificar_compatibilidad_proyecto(proyecto: dict, catalogo_pm: list[dict]) -> list[str]:
    """
    Compara cada código que Claude usó en `materiales` contra sus medidas
    REALES en el catálogo, y verifica que coincidan con lo declarado en
    `layout`. Esto atrapa un error que el validador estructural NO detecta
    hoy: que Claude use un larguero de 1594mm mientras el layout dice
    frente_mm=1894 (código real que existe, pero no es el que corresponde).

    Devuelve lista de errores; vacía = todo coherente.
    """
    errores: list[str] = []
    layout = proyecto.get("layout", {}) or {}
    frente_layout = layout.get("frente_mm")
    fondo_layout = layout.get("fondo_mm")
    peralte_layout = layout.get("peralte_larguero_mm")

    indice = {_sku_de(p): p for p in catalogo_pm if _sku_de(p)}

    for m in proyecto.get("materiales", []) or []:
        codigo = m.get("codigo")
        pieza = indice.get(codigo)
        if not pieza:
            continue  # código inexistente ya lo marca validador_engine, no lo dupliquemos aquí

        categoria = pieza.get("categoria")

        if categoria == "larguero":
            frente_real = pieza.get("frente_mm")
            if frente_real is not None and frente_layout is not None and frente_real != frente_layout:
                errores.append(
                    f"Incompatibilidad: '{codigo}' es un larguero de {frente_real}mm de frente, "
                    f"pero el layout declara frente_mm={frente_layout}. No es la pieza que corresponde."
                )
            peralte_real = pieza.get("peralte_mm")
            if peralte_real is not None and peralte_layout is not None and peralte_real != peralte_layout:
                errores.append(
                    f"Incompatibilidad: '{codigo}' tiene peralte {peralte_real}mm, "
                    f"pero el layout declara peralte_larguero_mm={peralte_layout}."
                )

        elif categoria == "cabecera":
            fondo_real = pieza.get("fondo_mm")
            if fondo_real is not None and fondo_layout is not None and fondo_real != fondo_layout:
                errores.append(
                    f"Incompatibilidad: '{codigo}' es una cabecera de fondo {fondo_real}mm, "
                    f"pero el layout declara fondo_mm={fondo_layout}."
                )

    return errores
