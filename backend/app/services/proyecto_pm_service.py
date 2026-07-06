"""
Orquestador del proyectista PM — motor de rack-bot adaptado a este backend.

Llama a Claude con visión directa (imágenes/PDF sin OCR de por medio),
extrae los bloques de la respuesta, valida contra las reglas estructurales
reales (validador.py, 647 líneas: frentes/fondos, cargadores, anclaje,
NOM-251 alimentos, NOM-006 defensas...), corre el pipeline determinista
(modelo 3D real con trimesh + planos PDF de 4 hojas + XLSX) y registra todo
en Supabase (pm_rackbot.historial_service).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from .pm_rackbot import claude_client, pipeline, validador
from .pm_rackbot import historial_service as historial
from .pm_rackbot import correcciones_pm_service as correcciones
from .pm_rackbot.utils import extraer_html, extraer_json, trocear
from .pm_rackbot.adaptador_visor import layout_a_matriz_ensamble_3d
from .catalogo_service import consultar_catalogo_piezas
from .reglas_service import obtener_ultimo_diseno
from ..clients import supabase
from ..config import URL_FRONTEND

log = logging.getLogger("proyecto_pm_service")


@dataclass
class ResultadoProyectoPM:
    partes_texto: list[str] = field(default_factory=list)   # narrativa troceada, lista para mandar por Telegram
    validacion_texto: list[str] | None = None                # resumen del validador (si hay proyecto), troceado
    proyecto: dict | None = None
    archivos: list[Path] = field(default_factory=list)       # PDF/XLSX/GLB/DAE/PNG generados (temporales)
    link_visor_3d: str | None = None                          # enlace al visor 3D de GitHub Pages (mismo del modo /rack)
    historial_id: int | None = None
    error: str | None = None


async def generar_proyecto_pm(
    descripcion: str,
    imagenes: list[tuple[str, bytes]],
    pdfs: list[bytes],
    session_id: str,
    tg_user_id: int | None,
    tg_username: str | None,
    tg_full_name: str | None,
) -> ResultadoProyectoPM:
    """
    Pipeline completo de un turno del proyectista PM. Los archivos generados
    quedan en un directorio temporal persistente — el llamador debe enviarlos
    y luego limpiarlos con `limpiar_temporales(resultado)`.
    """
    n_imgs, n_pdfs = len(imagenes), len(pdfs)

    # --- Contexto de corrección: si ya hay un proyecto previo en esta sesión,
    # se lo mandamos a Claude para que decida si es un ajuste al mismo diseño
    # o una petición nueva (el prompt de sistema ya trae esa instrucción).
    proyecto_anterior_row = historial.ultimo_proyecto_de_sesion(session_id)
    proyecto_anterior = proyecto_anterior_row.get("proyecto_json") if proyecto_anterior_row else None

    descripcion_para_claude = descripcion
    if proyecto_anterior:
        descripcion_para_claude = (
            "[Contexto: ya existe un proyecto previo para este cliente en esta conversación. "
            "Si el mensaje de abajo es un ajuste sobre él, aplica el punto 2 del checklist "
            "(recalcula solo lo necesario y conserva la misma 'clave', sube la 'revision'). "
            "Si es una petición distinta, ignora este contexto y arma un proyecto nuevo con clave nueva.]\n\n"
            f"JSON del proyecto anterior:\n{json.dumps(proyecto_anterior, ensure_ascii=False)}\n\n"
            f"Mensaje del cliente:\n{descripcion}"
        )

    try:
        texto, input_tokens, output_tokens = await claude_client.generar(descripcion_para_claude, imagenes, pdfs)
    except Exception as e:
        log.exception("claude_client.generar falló")
        historial.registrar(
            tg_user_id=tg_user_id, tg_username=tg_username, tg_full_name=tg_full_name,
            descripcion=descripcion or "", respuesta_texto="", proyecto_json=None,
            render_html=None, archivos_pipeline=None,
            n_imagenes=n_imgs, n_pdfs=n_pdfs, error=str(e)[:300],
            session_id=session_id,
        )
        return ResultadoProyectoPM(error=str(e))

    # Separamos los bloques: render HTML (se descarta; el pipeline genera uno
    # determinista desde el GLB real), JSON del proyecto, y el texto restante.
    html, texto = extraer_html(texto)
    proyecto, texto = extraer_json(texto)

    resultado = ResultadoProyectoPM(
        partes_texto=trocear(texto or "Listo."),
        proyecto=proyecto,
    )

    if proyecto:
        try:
            validacion = validador.validar(proyecto)
            log.info("Validación: %s", validacion.resumen())
            if validacion.errores or validacion.advertencias:
                resultado.validacion_texto = trocear(validacion.como_texto())
                # Opción B: se guarda solo, sin que nadie escriba nada — mide
                # qué tan seguido Claude se equivoca (control de calidad),
                # a diferencia de la corrección manual (lo que pide el cliente).
                correcciones.registrar_correccion_automatica(
                    session_id=session_id, tg_user_id=tg_user_id,
                    tipo=proyecto.get("especificacion") or (proyecto.get("layout") or {}).get("tipo"),
                    clave=proyecto.get("clave"),
                    detalle_validacion=validacion.como_texto(),
                    proyecto=proyecto,
                )
        except Exception as e:  # noqa: BLE001 — el validador no debe romper el flujo
            log.exception("validador falló: %s", e)

        # --- Corrección: si el proyecto conserva la misma clave del anterior,
        # Claude decidió que era un ajuste — lo guardamos en correcciones_armado.
        if correcciones.es_correccion(proyecto_anterior, proyecto):
            correcciones.registrar_correccion(
                session_id=session_id, tg_user_id=tg_user_id,
                tipo=proyecto.get("especificacion") or (proyecto.get("layout") or {}).get("tipo"),
                clave=proyecto.get("clave"),
                comentario_cliente=descripcion,
                proyecto_antes=proyecto_anterior, proyecto_despues=proyecto,
            )
            log.info("Corrección manual registrada para clave=%s", proyecto.get("clave"))

        # --- Visor 3D: mismo visor de GitHub Pages que usaba el agente rápido ---
        # Traducimos layout+materiales a marcos/vigas/mensulas y lo guardamos
        # en disenos_racks, versionado por session_id.
        try:
            catalogo_piezas = consultar_catalogo_piezas()
            matriz = layout_a_matriz_ensamble_3d(proyecto, catalogo_piezas)
            diseno_previo = obtener_ultimo_diseno(session_id)
            proxima_version = (diseno_previo["version_actual"] + 1) if diseno_previo else 1

            supabase.table("disenos_racks").insert({
                "vendedor_id": tg_username or tg_full_name or str(tg_user_id),
                "session_id": session_id,
                "solicitud_original": descripcion,
                "version_actual": proxima_version,
                "matriz_ensamble_3d": matriz,
                "historial_comentarios": {"comentario": descripcion, "clave_proyecto": proyecto.get("clave")},
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }).execute()

            sb_url = os.getenv("SUPABASE_URL", "")
            sb_key = os.getenv("SUPABASE_KEY", "")
            encoded_url = urllib.parse.quote_plus(sb_url)
            encoded_key = urllib.parse.quote_plus(sb_key)
            resultado.link_visor_3d = f"{URL_FRONTEND}?sb_url={encoded_url}&sb_key={encoded_key}&session_id={session_id}"
        except Exception as e:  # noqa: BLE001 — si falla, seguimos sin el link, no rompe el resto
            log.exception("No se pudo guardar en disenos_racks para el visor 3D: %s", e)

        work = Path(tempfile.mkdtemp(prefix="pm_rackbot_"))
        try:
            salidas = await asyncio.to_thread(pipeline.correr_pipeline, proyecto, work)
            log.info("Pipeline generó %d archivo(s)", len(salidas))

            # El render_3d_*.html del pipeline ya no se manda: el enlace del
            # visor de GitHub Pages (arriba) hace ese trabajo ahora.
            salidas = [p for p in salidas if p.suffix.lower() != ".html"]

            # Movemos a un directorio persistente ANTES de borrar work/, para
            # que el handler de Telegram pueda enviarlos después de retornar.
            persist = Path(tempfile.mkdtemp(prefix="pm_rackbot_persist_"))
            moved = []
            for p in salidas:
                try:
                    dst = persist / p.name
                    dst.write_bytes(p.read_bytes())
                    moved.append(dst)
                except Exception as e:  # noqa: BLE001
                    log.warning("no se pudo persistir %s: %s", p.name, e)
            resultado.archivos = moved

            if not moved and not resultado.link_visor_3d:
                extra = "⚠️ No pude generar planos/renders (¿faltan dependencias en el servidor?)."
                resultado.validacion_texto = (resultado.validacion_texto or []) + [extra]
        except Exception as e:  # noqa: BLE001
            log.exception("pipeline falló")
            extra = f"⚠️ Error generando planos/renders: {e}"
            resultado.validacion_texto = (resultado.validacion_texto or []) + [extra]
        finally:
            shutil.rmtree(work, ignore_errors=True)

    resultado.historial_id = historial.registrar(
        tg_user_id=tg_user_id, tg_username=tg_username, tg_full_name=tg_full_name,
        descripcion=descripcion or "", respuesta_texto=texto or "",
        proyecto_json=proyecto, render_html=html,
        archivos_pipeline=resultado.archivos,
        n_imagenes=n_imgs, n_pdfs=n_pdfs,
        session_id=session_id,
    )
    return resultado


def limpiar_temporales(resultado: ResultadoProyectoPM) -> None:
    """Borra el directorio temporal 'persist' con los archivos generados, ya enviados por Telegram."""
    if resultado.archivos:
        try:
            shutil.rmtree(resultado.archivos[0].parent, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass
