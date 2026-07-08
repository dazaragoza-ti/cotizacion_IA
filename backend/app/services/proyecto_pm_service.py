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
import logging
import os
import shutil
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

from ..ai.clients import claude_client

from ..ai.pipelines import pipeline

from ..engineering import validator_engine
from ..engineering.compatibility import verificar_compatibilidad_proyecto
from . import historial_service as historial
from . import correcciones_pm_service as correcciones
from ..engineering.correction_processor import correction_processor
from .catalogo_pm_service import consultar_catalogo_pm
from ..ai.pipelines.utils import extraer_html, extraer_json, trocear
from ..ai.adapters.adaptador_visor import layout_a_matriz_ensamble_3d
from ..ai.rag.vector_store import vector_store
from ..ai.context_builder import construir_descripcion_extendida
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


MAX_INTENTOS_DISENO = 2  # 1 intento normal + 1 reintento si hay errores bloqueantes


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

    Si el validador o el Compatibility Engine encuentran errores BLOQUEANTES
    (no simples advertencias), el diseño se le regresa a Claude una vez más
    con el detalle de qué corregir, antes de dárselo al cliente — así como
    lo describe el Capítulo 6.4 del manual: "si existe un error, el diseño
    vuelve al proyectista". Máximo `MAX_INTENTOS_DISENO` llamadas a Claude
    por turno, para no generar un loop infinito ni disparar el costo.
    """
    n_imgs, n_pdfs = len(imagenes), len(pdfs)

    # --- Contexto de corrección: si ya hay un proyecto previo en esta sesión,
    # se lo mandamos a Claude para que decida si es un ajuste al mismo diseño
    # o una petición nueva (el prompt de sistema ya trae esa instrucción).
    proyecto_anterior_row = historial.ultimo_proyecto_de_sesion(session_id)
    proyecto_anterior = proyecto_anterior_row.get("proyecto_json") if proyecto_anterior_row else None

    # --- RAG: correcciones parecidas por similitud semántica (no por clave) ---
    # Busca en correcciones_armado (vectorizadas) casos donde un cliente pidió
    # algo parecido antes, sin importar si es el mismo proyecto o uno nuevo.
    # Si Supabase todavía no tiene el RPC match_knowledge o la tabla está
    # vacía, esto falla silencioso y el flujo sigue igual que antes.
    try:
        correcciones_similares = vector_store.search(descripcion, top_k=5, tipo="correccion")
    except Exception as e:  # noqa: BLE001
        log.warning("Búsqueda RAG de correcciones falló (¿falta el RPC match_knowledge en Supabase?): %s", e)
        correcciones_similares = []

    # --- Context Builder: junta proyecto anterior + catálogo filtrado por el
    # Compatibility Engine + correcciones RAG en un solo texto consistente.
    # No decide nada — solo arma lo que ya recuperaron los demás motores.
    catalogo_pm_para_contexto = consultar_catalogo_pm() if proyecto_anterior else None
    descripcion_para_claude = construir_descripcion_extendida(
        descripcion=descripcion,
        proyecto_anterior=proyecto_anterior,
        correcciones_similares=correcciones_similares,
        catalogo_pm=catalogo_pm_para_contexto,
    )

    texto = html = None
    proyecto: dict | None = None
    input_tokens = output_tokens = 0
    errores_bloqueantes: list[str] = []
    avisos: list[str] = []

    for intento in range(1, MAX_INTENTOS_DISENO + 1):
        try:
            texto, input_tokens, output_tokens = await claude_client.generar(
                descripcion_para_claude, imagenes, pdfs,
                langsmith_extra={
                    "metadata": {
                        "session_id": session_id, "tg_user_id": tg_user_id,
                        "tg_username": tg_username, "n_imagenes": n_imgs, "n_pdfs": n_pdfs,
                        "intento": intento,
                    }
                },
            )
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

        errores_bloqueantes = []
        avisos = []

        if proyecto:
            try:
                validacion = validator_engine.validar(proyecto)
                log.info("Intento %d — Validación: %s", intento, validacion.resumen())
                errores_bloqueantes.extend(validacion.errores)
                avisos.extend(validacion.advertencias)

                # --- Compatibility Engine: determinista, sin IA — verifica que los
                # códigos que Claude eligió coincidan de verdad con las medidas
                # reales del catálogo (no solo que "existan", como ya hace el
                # validador estructural). Un mismatch de medidas SÍ es bloqueante.
                catalogo_pm_actual = consultar_catalogo_pm()
                errores_bloqueantes.extend(verificar_compatibilidad_proyecto(proyecto, catalogo_pm_actual))
            except Exception as e:  # noqa: BLE001 — el validador no debe romper el flujo
                log.exception("validador falló: %s", e)

        if not errores_bloqueantes or intento >= MAX_INTENTOS_DISENO:
            break

        log.warning("Intento %d con errores bloqueantes, se le regresan a Claude: %s", intento, errores_bloqueantes)
        descripcion_para_claude = (
            f"{descripcion_para_claude}\n\n"
            "[El diseño que acabas de generar tiene errores que debes corregir. "
            "Genera el proyecto COMPLETO otra vez (mismo nivel de detalle: diseño, "
            "supuestos, despiece, cotización, JSON), corrigiendo específicamente esto:]\n"
            + "\n".join(f"- {e}" for e in errores_bloqueantes)
        )

    resultado = ResultadoProyectoPM(
        partes_texto=trocear(texto or "Listo."),
        proyecto=proyecto,
    )

    if proyecto:
        # Sprint 2: cada SKU del despiece suma veces_usado (best-effort, no rompe).
        correction_processor.registrar_uso(proyecto)
        texto_validacion = ""
        if errores_bloqueantes or avisos:
            texto_validacion = validator_engine.ResultadoValidacion(
                errores=[e for e in errores_bloqueantes if "Incompatibilidad" not in e],
                advertencias=avisos,
            ).como_texto()
            compat_solo = [e for e in errores_bloqueantes if "Incompatibilidad" in e]
            if compat_solo:
                texto_validacion += "\n\n⚙️ Compatibility Engine:\n" + "\n".join(f"- {e}" for e in compat_solo)

        if texto_validacion.strip():
            resultado.validacion_texto = trocear(texto_validacion.strip())
            # Opción B: se guarda solo, sin que nadie escriba nada — mide
            # qué tan seguido Claude se equivoca (control de calidad),
            # a diferencia de la corrección manual (lo que pide el cliente).
            # Si hubo reintento y de todos modos quedaron errores, esto es
            # justo lo que no se pudo autocorregir — vale la pena auditarlo.
            try:
                correction_processor.process_automatica(
                    session_id=session_id, tg_user_id=tg_user_id,
                    tipo=proyecto.get("especificacion") or (proyecto.get("layout") or {}).get("tipo"),
                    clave=proyecto.get("clave"),
                    detalle_validacion=texto_validacion.strip(),
                    proyecto=proyecto,
                )
            except Exception as e:  # noqa: BLE001
                log.exception("process_automatica falló: %s", e)

        # --- Corrección: si el proyecto conserva la misma clave del anterior,
        # Claude decidió que era un ajuste — lo guardamos en correcciones_armado.
        if correcciones.es_correccion(proyecto_anterior, proyecto):
            correction_processor.process(
                session_id=session_id, tg_user_id=tg_user_id,
                tipo=proyecto.get("especificacion") or (proyecto.get("layout") or {}).get("tipo"),
                clave=proyecto.get("clave"),
                comentario_cliente=descripcion,
                proyecto_antes=proyecto_anterior, proyecto_despues=proyecto,
            )
            log.info("Corrección manual procesada para clave=%s", proyecto.get("clave"))

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
