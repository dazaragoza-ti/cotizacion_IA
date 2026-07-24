"""
Context Builder — Capítulo 4.16 del AI_ENGINEERING_MANUAL.md.

Responsabilidad única: construir el texto de contexto que se le agrega al
mensaje del cliente antes de mandarlo a Claude. NO decide, NO calcula, NO
valida — solo junta lo que ya recuperaron otros motores (proyecto anterior,
correcciones por RAG, catálogo filtrado por el Compatibility Engine, relaciones
aprendidas del Knowledge Graph, reglas permanentes de `reglas_armado`) en un
formato consistente.

Antes esto vivía disperso como concatenación de strings directamente dentro
de proyecto_pm_service.py. Se extrajo aquí para que sea una sola función
testeable, en vez de lógica de formato mezclada con la orquestación del
pipeline completo.
"""
from __future__ import annotations

import json

from ..engineering.compatibility import inferir_familia, piezas_compatibles
from ..engineering.sku_diff import extraer_piezas
from ..services.reglas_service import consultar_reglas_armado
from .rag.graph import knowledge_graph

# Top-N: evita dumps ilimitados al prompt del proyectista (ahorro de tokens).
MAX_REGLAS_ARMADO = 15
MAX_RELACIONES_GRAFO = 8
MAX_CORRECCIONES_RAG = 3
MAX_CHARS_POR_CORRECCION = 1200
MAX_MANUALES_RAG = 4
MAX_CHARS_POR_MANUAL = 1800


def _inferir_tipo_rack(
    descripcion: str,
    proyecto_anterior: dict | None,
) -> str:
    """Tipo canónico para filtrar `reglas_armado`:
    pesada | ligera | cantilever | entrepiso | todos.
    """
    if proyecto_anterior:
        from ..engineering.tipo_rack import tipo_rack_de_proyecto
        tip = tipo_rack_de_proyecto(proyecto_anterior, default="")
        if tip and tip != "todos":
            return tip

    from ..engineering.tipo_rack import normalizar_tipo_rack
    return normalizar_tipo_rack(descripcion, default="todos")


def _bloque_reglas_armado(tipo_rack: str, *, max_reglas: int = MAX_REGLAS_ARMADO) -> str:
    """Cierra el bucle de LECTURA de `reglas_armado`: PromotionEngine ya
    materializa relaciones permanentes ahí, pero hasta ahora nadie las
    devolvía al prompt del proyectista. Reusa `consultar_reglas_armado`.
    """
    try:
        reglas = consultar_reglas_armado(tipo_rack)
    except Exception:  # noqa: BLE001 — best-effort; no tumbar el prompt
        return ""

    if not reglas:
        return ""

    lineas: list[str] = []
    for regla in reglas[:max_reglas]:
        condicion = (regla.get("condicion") or "").strip()
        descripcion = (regla.get("descripcion") or "").strip()
        accion = (regla.get("accion") or "").strip()
        partes_regla = [p for p in (condicion, descripcion) if p]
        cabeza = " — ".join(partes_regla) if partes_regla else "(sin descripción)"
        cola = f" → {accion}" if accion else ""
        lineas.append(f"- {cabeza}{cola}")

    if not lineas:
        return ""

    return (
        "[Reglas de armado activas (tabla reglas_armado) — obligatorias; "
        "aplícalas con la misma prioridad que el checklist del system prompt; "
        "las promovidas desde el historial de correcciones ya están validadas]\n"
        + "\n".join(lineas)
    )


def _bloque_relaciones_grafo(skus: list[str], *, max_relaciones: int = MAX_RELACIONES_GRAFO) -> str:
    """Cierra el bucle de LECTURA del grafo (Sprint 2, Fase 3): hasta ahora
    `knowledge_graph` era write-only — las relaciones que aprendía
    CorrectionProcessor nunca volvían a influir en lo que Claude ve. Aquí se
    consultan las relaciones ya reforzadas (reemplaza_por / evitar_con /
    compatible_con) de los SKUs del proyecto anterior y se inyectan al prompt.
    """
    lineas: list[str] = []
    for sku in skus:
        for rel in knowledge_graph.relaciones_relevantes("sku", sku):
            confidence = rel.get("confidence") or 0
            marca = " (regla validada)" if rel.get("validada") else ""
            lineas.append(
                f"- {rel.get('from_id')} {rel.get('relation')} {rel.get('to_id')} "
                f"(confidence={confidence:.2f}{marca})"
            )
            if len(lineas) >= max_relaciones:
                break
        if len(lineas) >= max_relaciones:
            break

    if not lineas:
        return ""

    return (
        "[Relaciones aprendidas del historial de correcciones (Knowledge Graph) — "
        "patrones reales detectados entre piezas de este proyecto; considéralos "
        "con la misma prioridad que las correcciones aprendidas de abajo]\n"
        + "\n".join(lineas)
    )


def _bloque_correcciones_rag(
    correcciones_similares: list[dict],
    *,
    max_correcciones: int = MAX_CORRECCIONES_RAG,
    max_chars: int = MAX_CHARS_POR_CORRECCION,
) -> str:
    """Top-N correcciones RAG, truncadas por corrección."""
    trozos: list[str] = []
    for c in correcciones_similares[:max_correcciones]:
        texto = (c.get("contenido") or "").strip()
        if not texto:
            continue
        if len(texto) > max_chars:
            texto = texto[: max_chars - 1] + "…"
        trozos.append(texto)
    if not trozos:
        return ""
    return (
        "[Correcciones aprendidas de casos parecidos anteriores — aplícalas si el caso "
        "coincide, tienen prioridad sobre el criterio general porque ya fueron validadas "
        "en la práctica]\n" + "\n\n".join(trozos)
    )


def _bloque_manuales_rag(
    manuales: list[dict] | None,
    *,
    max_manuales: int = MAX_MANUALES_RAG,
    max_chars: int = MAX_CHARS_POR_MANUAL,
) -> str:
    """Fichas técnicas vía RAG (`tipo=manual`). Sustituyen el embed en system prompt."""
    if not manuales:
        return ""
    trozos: list[str] = []
    for m in manuales[:max_manuales]:
        texto = (m.get("contenido") or "").strip()
        if not texto:
            continue
        if len(texto) > max_chars:
            texto = texto[: max_chars - 1] + "…"
        ref = (m.get("referencia_id") or m.get("fuente") or "ficha").strip()
        trozos.append(f"### {ref}\n{texto}")
    if not trozos:
        return ""
    return (
        "[Fichas técnicas relevantes (RAG tipo=manual) — verdad técnica PM; "
        "prioridad sobre memoria del modelo; aplica reglas de decisión al pie de la letra]\n"
        + "\n\n".join(trozos)
    )


def armar_mensaje_reintento(
    descripcion_base: str,
    proyecto_previo: dict | None,
    errores: list[str],
) -> str:
    """Reinyecta JSON previo + errores tipados (no pide diseño desde cero)."""
    errores_txt = "\n".join(f"- {e}" for e in errores)
    json_previo = (
        json.dumps(proyecto_previo, ensure_ascii=False, separators=(",", ":"))
        if proyecto_previo
        else "(no hubo JSON parseable en el intento anterior)"
    )
    return (
        f"{descripcion_base}\n\n"
        "[Corrección de contrato/validación — NO redesignes desde cero. "
        "Parte del JSON previo, corrige solo lo indicado por los errores tipados "
        "y devuelve el proyecto JSON completo ya corregido (más el resto del entregable).]\n\n"
        f"JSON previo a corregir:\n{json_previo}\n\n"
        f"Errores tipados:\n{errores_txt}"
    )


def construir_descripcion_extendida(
    descripcion: str,
    proyecto_anterior: dict | None,
    correcciones_similares: list[dict] | None,
    catalogo_pm: list[dict] | None = None,
    tipo_rack: str | None = None,
    manuales_rag: list[dict] | None = None,
) -> str:
    """
    Arma el texto final que se le manda a Claude, agregando (en este orden):

    1. Contexto de corrección — si hay un proyecto anterior en la sesión.
    2. Catálogo pre-filtrado por Compatibility Engine (familia + medidas del
       proyecto previo). Complementa el subset familia+comunes que ya va en el
       system vía claude_client (aquí se estrecha aún más por frente/fondo).
    3. Relaciones aprendidas del Knowledge Graph (top-N).
    4. Reglas de armado activas (top-N).
    5. Fichas técnicas RAG (`tipo=manual`, top-N).
    6. Correcciones RAG similares (top-N, truncadas).

    Si no hay nada que agregar, devuelve `descripcion` tal cual.
    """
    partes: list[str] = []

    if proyecto_anterior:
        partes.append(
            "[Contexto: ya existe un proyecto previo para este cliente en esta conversación. "
            "Si el mensaje de abajo es un ajuste sobre él, aplica el punto 2 del checklist "
            "(recalcula solo lo necesario y conserva la misma 'clave', sube la 'revision'). "
            "Si es una petición distinta, ignora este contexto y arma un proyecto nuevo con clave nueva.]\n\n"
            f"JSON del proyecto anterior:\n{json.dumps(proyecto_anterior, ensure_ascii=False)}"
        )

        # Compatibility Engine: estrecha por medidas del proyecto anterior.
        if catalogo_pm:
            layout_anterior = proyecto_anterior.get("layout", {}) or {}
            familia = inferir_familia(descripcion, proyecto_anterior)

            if familia:
                compatibles = piezas_compatibles(
                    catalogo_pm, familia,
                    frente_mm=layout_anterior.get("frente_mm"),
                    fondo_mm=layout_anterior.get("fondo_mm"),
                    peralte_mm=layout_anterior.get("peralte_larguero_mm"),
                )
                total = len(compatibles["cabeceras"]) + len(compatibles["largueros"]) + len(compatibles["comunes"])
                if total > 0:
                    partes.append(
                        f"[Piezas compatibles con este proyecto (familia={familia}, "
                        f"frente={layout_anterior.get('frente_mm')}mm, fondo={layout_anterior.get('fondo_mm')}mm), "
                        f"filtradas por el Compatibility Engine — prioriza estas sobre el resto del catálogo si el "
                        f"ajuste no cambia las medidas base:]\n"
                        + json.dumps(compatibles, ensure_ascii=False, separators=(",", ":"))
                    )

        skus_previos = list(extraer_piezas(proyecto_anterior).keys())
        if skus_previos:
            try:
                bloque_grafo = _bloque_relaciones_grafo(skus_previos)
            except Exception:  # noqa: BLE001 — el grafo nunca debe tumbar la generación
                bloque_grafo = ""
            if bloque_grafo:
                partes.append(bloque_grafo)

    tipo = tipo_rack or _inferir_tipo_rack(descripcion, proyecto_anterior)
    bloque_reglas = _bloque_reglas_armado(tipo)
    if bloque_reglas:
        partes.append(bloque_reglas)

    bloque_manuales = _bloque_manuales_rag(manuales_rag)
    if bloque_manuales:
        partes.append(bloque_manuales)

    if correcciones_similares:
        bloque = _bloque_correcciones_rag(correcciones_similares)
        if bloque:
            partes.append(bloque)

    if not partes:
        return descripcion

    return "\n\n".join(partes) + f"\n\nMensaje del cliente:\n{descripcion}"
