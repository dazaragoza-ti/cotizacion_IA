"""
Context Builder — Capítulo 4.16 del AI_ENGINEERING_MANUAL.md.

Responsabilidad única: construir el texto de contexto que se le agrega al
mensaje del cliente antes de mandarlo a Claude. NO decide, NO calcula, NO
valida — solo junta lo que ya recuperaron otros motores (proyecto anterior,
correcciones por RAG, catálogo filtrado por el Compatibility Engine, relaciones
aprendidas del Knowledge Graph) en un formato consistente.

Antes esto vivía disperso como concatenación de strings directamente dentro
de proyecto_pm_service.py. Se extrajo aquí para que sea una sola función
testeable, en vez de lógica de formato mezclada con la orquestación del
pipeline completo.
"""
from __future__ import annotations

import json

from ..engineering.compatibility import piezas_compatibles
from ..engineering.sku_diff import extraer_piezas
from .rag.graph import knowledge_graph


def _bloque_relaciones_grafo(skus: list[str], *, max_relaciones: int = 10) -> str:
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


def construir_descripcion_extendida(
    descripcion: str,
    proyecto_anterior: dict | None,
    correcciones_similares: list[dict] | None,
    catalogo_pm: list[dict] | None = None,
) -> str:
    """
    Arma el texto final que se le manda a Claude, agregando (en este orden):

    1. Contexto de corrección — si hay un proyecto anterior en la sesión.
    2. Catálogo pre-filtrado — SOLO si ya conocemos familia/frente/fondo
       (o sea, solo en el caso de corrección; en un proyecto nuevo no hay
       nada que filtrar todavía, así que Claude sigue viendo el catálogo
       completo vía claude_client — este bloque es un complemento, no un
       reemplazo).
    3. Relaciones aprendidas del Knowledge Graph para los SKUs del proyecto
       anterior (reemplaza_por / evitar_con / compatible_con).
    4. Correcciones aprendidas por similitud semántica (RAG).

    Si no hay nada que agregar, devuelve `descripcion` tal cual — el
    contexto nunca resta información, solo suma cuando hay algo real que sumar.
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

        # Compatibility Engine: ya sabemos familia/frente/fondo del proyecto
        # anterior — dale a Claude solo las piezas que de verdad aplican,
        # en vez de las 79 completas (menos tokens, cero ambigüedad).
        if catalogo_pm:
            layout_anterior = proyecto_anterior.get("layout", {}) or {}
            especificacion = (proyecto_anterior.get("especificacion") or "").lower()
            familia = "pesada" if "pesada" in especificacion else ("ligera" if "ligera" in especificacion else None)

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
                        + json.dumps(compatibles, ensure_ascii=False)
                    )

        skus_previos = list(extraer_piezas(proyecto_anterior).keys())
        if skus_previos:
            try:
                bloque_grafo = _bloque_relaciones_grafo(skus_previos)
            except Exception:  # noqa: BLE001 — el grafo nunca debe tumbar la generación
                bloque_grafo = ""
            if bloque_grafo:
                partes.append(bloque_grafo)

    if correcciones_similares:
        bloque = "\n\n".join(
            c.get("contenido", "").strip() for c in correcciones_similares if c.get("contenido")
        )
        if bloque:
            partes.append(
                "[Correcciones aprendidas de casos parecidos anteriores — aplícalas si el caso "
                "coincide, tienen prioridad sobre el criterio general porque ya fueron validadas "
                "en la práctica]\n" + bloque
            )

    if not partes:
        return descripcion

    return "\n\n".join(partes) + f"\n\nMensaje del cliente:\n{descripcion}"
