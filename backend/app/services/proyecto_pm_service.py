"""
Orquestador del proyectista PM (motor de rack-bot adaptado a este backend).

Llama a Claude con vision directa (imagenes/PDF sin OCR de por medio),
extrae los bloques de la respuesta, valida contra las reglas estructurales
reales (validador.py, corre el pipeline determinista (modelo 3D real con
trimesh + planos PDF de 4 hojas + XLSX) y registra todo en Supabase.
"""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..ai.clients import claude_client, ventas_client, qa_visual_client

from ..ai.pipelines import pipeline

from ..engineering import validator_engine
from ..engineering.compatibility import (
    filtrar_catalogo_por_familia,
    inferir_familia,
    verificar_compatibilidad_proyecto,
)
from . import historial_service as historial
from . import correcciones_pm_service as correcciones
from ..engineering.correction_processor import correction_processor
from .catalogo_pm_service import consultar_catalogo_pm
from ..ai.pipelines.utils import extraer_html, extraer_json, trocear
from ..ai.adapters.adaptador_visor import layout_a_matriz_ensamble_3d
from ..ai.rag.vector_store import vector_store
from ..ai.context_builder import (
    MAX_CORRECCIONES_RAG,
    armar_mensaje_reintento,
    construir_descripcion_extendida,
)
from ..ai.schemas.proyecto_pm import errores_contrato_proyecto
from .catalogo_service import consultar_catalogo_piezas
from .reglas_service import obtener_ultimo_diseno
from . import ventas_service
from ..clients import supabase
from ..config import URL_FRONTEND
from ..core import pipeline_tracer, error_logger

log = logging.getLogger("proyecto_pm_service")


@dataclass
class ResultadoProyectoPM:
    partes_texto: list[str] = field(default_factory=list)
    validacion_texto: list[str] | None = None
    errores_validacion: list[str] = field(default_factory=list)
    avisos_validacion: list[str] = field(default_factory=list)
    proyecto: dict | None = None
    archivos: list[Path] = field(default_factory=list)
    link_visor_3d: str | None = None
    historial_id: int | None = None
    error: str | None = None
    propuesta_comercial: str | None = None


MAX_INTENTOS_DISENO = 2


async def generar_proyecto_pm(
    descripcion: str,
    imagenes: list[tuple[str, bytes]],
    pdfs: list[bytes],
    session_id: str,
    tg_user_id: int | None,
    tg_username: str | None,
    tg_full_name: str | None,
) -> ResultadoProyectoPM:
    n_imgs, n_pdfs = len(imagenes), len(pdfs)

    # Traza en vivo de ESTA solicitud puntual (distinta de session_id, que
    # persiste entre varias solicitudes de la misma conversacion) -- ver
    # pipeline_tracer y el modulo Arquitectura del Sistema del frontend.
    solicitud_id = str(uuid.uuid4())
    pipeline_tracer.emitir(solicitud_id, "fastapi", "Solicitud recibida, orquestando el flujo", "completado")

    proyecto_anterior_row = historial.ultimo_proyecto_de_sesion(session_id)
    proyecto_anterior = proyecto_anterior_row.get("proyecto_json") if proyecto_anterior_row else None

    pipeline_tracer.emitir(solicitud_id, "rag", "Buscando correcciones similares (Voyage AI)", "en_progreso")
    try:
        correcciones_similares = vector_store.search(
            descripcion, top_k=MAX_CORRECCIONES_RAG, tipo="correccion",
        )
        pipeline_tracer.emitir(
            solicitud_id, "rag",
            f"{len(correcciones_similares)} correccion(es) similar(es) encontrada(s)", "completado",
        )
    except Exception as e:
        log.warning("Busqueda RAG de correcciones fallo: %s", e)
        correcciones_similares = []
        pipeline_tracer.emitir(solicitud_id, "rag", "Busqueda RAG fallo, se continua sin evidencia", "error")

    if proyecto_anterior:
        pipeline_tracer.emitir(solicitud_id, "graph", "Consultando relaciones aprendidas del proyecto anterior", "en_progreso")
    pipeline_tracer.emitir(solicitud_id, "context_builder", "Armando el prompt final para Claude", "en_progreso")
    catalogo_pm_completo = consultar_catalogo_pm()
    familia_catalogo = inferir_familia(descripcion, proyecto_anterior)
    catalogo_pm_filtrado, modo_filtro = filtrar_catalogo_por_familia(
        catalogo_pm_completo, familia_catalogo,
    )
    log.info("Catálogo para proyectista: modo=%s (%d piezas)", modo_filtro, len(catalogo_pm_filtrado))

    descripcion_base = construir_descripcion_extendida(
        descripcion=descripcion,
        proyecto_anterior=proyecto_anterior,
        correcciones_similares=correcciones_similares,
        catalogo_pm=catalogo_pm_completo if proyecto_anterior else None,
    )
    descripcion_para_claude = descripcion_base
    if proyecto_anterior:
        pipeline_tracer.emitir(solicitud_id, "graph", "Relaciones del grafo inyectadas al prompt", "completado")
    pipeline_tracer.emitir(solicitud_id, "context_builder", "Prompt listo para Claude", "completado")

    texto = html = None
    proyecto = None
    input_tokens = output_tokens = 0
    errores_bloqueantes = []
    avisos = []

    langsmith_run_id = uuid.uuid4()

    for intento in range(1, MAX_INTENTOS_DISENO + 1):
        pipeline_tracer.emitir(solicitud_id, "claude", f"Claude esta razonando el diseno (intento {intento})", "en_progreso")
        try:
            texto, input_tokens, output_tokens = await claude_client.generar(
                descripcion_para_claude, imagenes, pdfs,
                catalogo_pm=catalogo_pm_filtrado,
                langsmith_extra={
                    "run_id": langsmith_run_id,
                    "metadata": {
                        "session_id": session_id, "tg_user_id": tg_user_id,
                        "tg_username": tg_username, "n_imagenes": n_imgs, "n_pdfs": n_pdfs,
                        "intento": intento,
                        "catalogo_filtro": modo_filtro,
                    }
                },
            )
        except Exception as e:
            log.exception("claude_client.generar fallo")
            pipeline_tracer.emitir(solicitud_id, "claude", f"Claude fallo: {e}", "error")
            historial.registrar(
                tg_user_id=tg_user_id, tg_username=tg_username, tg_full_name=tg_full_name,
                descripcion=descripcion or "", respuesta_texto="", proyecto_json=None,
                render_html=None, archivos_pipeline=None,
                n_imagenes=n_imgs, n_pdfs=n_pdfs, error=str(e)[:300],
                session_id=session_id,
            )
            return ResultadoProyectoPM(error=str(e))
        pipeline_tracer.emitir(solicitud_id, "claude", "Claude genero el diseno", "completado")

        html, texto = extraer_html(texto)
        proyecto, texto = extraer_json(texto)

        errores_bloqueantes = []
        avisos = []

        # Contrato tipado del JSON (Pydantic) — antes del validador de
        # ingeniería: si faltan claves de layout/materiales, no tiene
        # sentido correr reglas estructurales sobre un dict incompleto.
        errores_contrato = errores_contrato_proyecto(proyecto)
        if errores_contrato:
            errores_bloqueantes.extend(errores_contrato)
            log.warning("Intento %d - Contrato JSON invalido: %s", intento, errores_contrato)

        if proyecto and not errores_contrato:
            pipeline_tracer.emitir(solicitud_id, "engineering", "Validando reglas de ingenieria (determinista)", "en_progreso")
            try:
                catalogo_pm_actual = catalogo_pm_completo or consultar_catalogo_pm()
                validacion = validator_engine.validar(proyecto, catalogo=catalogo_pm_actual)
                log.info("Intento %d - Validacion: %s", intento, validacion.resumen())
                errores_bloqueantes.extend(validacion.errores)
                avisos.extend(validacion.advertencias)

                errores_bloqueantes.extend(verificar_compatibilidad_proyecto(proyecto, catalogo_pm_actual))
            except Exception as e:
                log.exception("validador fallo: %s", e)
            pipeline_tracer.emitir(
                solicitud_id, "engineering",
                "Diseno aprobado" if not errores_bloqueantes else f"{len(errores_bloqueantes)} error(es), regresa a Claude",
                "completado" if not errores_bloqueantes else "error",
            )
        elif errores_contrato:
            pipeline_tracer.emitir(
                solicitud_id, "engineering",
                f"Contrato JSON invalido ({len(errores_contrato)} error(es))",
                "error",
            )

        if not errores_bloqueantes or intento >= MAX_INTENTOS_DISENO:
            break

        log.warning("Intento %d con errores bloqueantes, se regresan a Claude: %s", intento, errores_bloqueantes)
        # Parte de descripcion_base (sin apilar reintentos) + JSON previo + errores.
        descripcion_para_claude = armar_mensaje_reintento(
            descripcion_base, proyecto, errores_bloqueantes,
        )

    resultado = ResultadoProyectoPM(
        partes_texto=trocear(texto or "Listo."),
        proyecto=proyecto,
    )

    if proyecto:
        correction_processor.registrar_uso(proyecto)
        texto_validacion = ""
        if errores_bloqueantes or avisos:
            texto_validacion = validator_engine.ResultadoValidacion(
                errores=[e for e in errores_bloqueantes if "Incompatibilidad" not in e],
                advertencias=avisos,
            ).como_texto()
            compat_solo = [e for e in errores_bloqueantes if "Incompatibilidad" in e]
            if compat_solo:
                texto_validacion += "\n\nCompatibility Engine:\n" + "\n".join(f"- {e}" for e in compat_solo)

        resultado.errores_validacion = list(errores_bloqueantes)
        resultado.avisos_validacion = list(avisos)

        if texto_validacion.strip():
            resultado.validacion_texto = trocear(texto_validacion.strip())
            try:
                correction_processor.process_automatica(
                    session_id=session_id, tg_user_id=tg_user_id,
                    tipo=proyecto.get("especificacion") or (proyecto.get("layout") or {}).get("tipo"),
                    clave=proyecto.get("clave"),
                    detalle_validacion=texto_validacion.strip(),
                    proyecto=proyecto,
                )
            except Exception as e:
                log.exception("process_automatica fallo: %s", e)

        if correcciones.es_correccion(proyecto_anterior, proyecto):
            correction_processor.process(
                session_id=session_id, tg_user_id=tg_user_id,
                tipo=proyecto.get("especificacion") or (proyecto.get("layout") or {}).get("tipo"),
                clave=proyecto.get("clave"),
                comentario_cliente=descripcion,
                proyecto_antes=proyecto_anterior, proyecto_despues=proyecto,
            )
            log.info("Correccion manual procesada para clave=%s", proyecto.get("clave"))

        try:
            catalogo_piezas = consultar_catalogo_piezas()
            matriz = layout_a_matriz_ensamble_3d(proyecto, catalogo_piezas)
            diseno_previo = obtener_ultimo_diseno(session_id)
            proxima_version = (diseno_previo["version_actual"] + 1) if diseno_previo else 1

            # historial_comentarios es siempre una lista acumulada de strings
            # para que el frontend la pueda renderizar sin depender de la
            # forma del ultimo escritor.
            historial_previo = (diseno_previo.get("historial_comentarios") if diseno_previo else None) or []
            if not isinstance(historial_previo, list):
                historial_previo = [str(historial_previo)]
            clave_proyecto = proyecto.get("clave")
            comentario_historial = f"[{clave_proyecto}] {descripcion}" if clave_proyecto else descripcion
            historial_comentarios = [*historial_previo, comentario_historial]

            supabase.table("disenos_racks").insert({
                "vendedor_id": tg_username or tg_full_name or str(tg_user_id),
                "session_id": session_id,
                "solicitud_original": descripcion,
                "version_actual": proxima_version,
                "matriz_ensamble_3d": matriz,
                "historial_comentarios": historial_comentarios,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
            }).execute()

            try:
                supabase.table("disenos_racks").update({
                    "langsmith_run_id": str(langsmith_run_id),
                }).eq("session_id", session_id).eq("version_actual", proxima_version).execute()
            except Exception as e:
                log.warning("No se pudo persistir langsmith_run_id (falta migracion 0004?): %s", e)

            # El visor (frontend/index.html) ya trae la key anon de Supabase
            # hardcodeada como default -- es publica por diseno (protegida por
            # RLS, no por ocultarla). El link solo necesita el session_id, que
            # es lo unico que de verdad varia entre proyectos.
            resultado.link_visor_3d = f"{URL_FRONTEND}?session_id={session_id}"
        except Exception as e:
            log.exception("No se pudo guardar en disenos_racks para el visor 3D: %s", e)

        # Precio de cotizacion: nunca confiar en el que Claude copio en su JSON
        # (puede venir de memoria/RAG desactualizado) -- se sobreescribe con el
        # precio real y actual de Supabase (catalogo_pm) por codigo de SKU,
        # misma logica de "ingenieria antes que el modelo" que ya usa el
        # Validator Engine. Si un codigo no esta en el catalogo, se deja el
        # precio que trajo Claude en vez de tumbar la cotizacion completa.
        try:
            precios_reales = {
                fila["codigo"]: fila["precio"]
                for fila in consultar_catalogo_pm()
                if fila.get("codigo") and fila.get("precio") is not None
            }
            for material in proyecto.get("materiales", []) or []:
                precio_real = precios_reales.get(material.get("codigo"))
                if precio_real is not None:
                    material["precio"] = precio_real
        except Exception as e:
            log.warning("No se pudo verificar precios contra catalogo_pm, se usan los del JSON: %s", e)

        # Cotizador IA / Ventas (Cap. 7.12): segundo agente, dominio de negocio
        # (descuentos, historial de cliente) -- nunca calcula ingenieria ni
        # toca el proyecto tecnico. El monto y el descuento son deterministas
        # (ventas_service.py); Claude solo redacta el texto persuasivo.
        pipeline_tracer.emitir(solicitud_id, "ventas", "Calculando descuento y propuesta comercial", "en_progreso")
        descuento_pct, motivo_descuento = 0.0, ""
        try:
            monto_total = sum(
                float(m.get("pzas") or 0) * float(m.get("precio") or 0)
                for m in (proyecto.get("materiales", []) or [])
            )
            cliente_id = ventas_service.buscar_o_crear_cliente(proyecto.get("cliente") or "")
            if cliente_id and monto_total > 0:
                hist = ventas_service.historial_cliente(cliente_id)
                descuento_pct, motivo_descuento = ventas_service.calcular_descuento(
                    monto_total, hist["monto_total_historico"],
                )
                resultado.propuesta_comercial = await ventas_client.generar_propuesta_comercial(
                    proyecto=proyecto, monto_total=monto_total,
                    descuento_pct=descuento_pct, motivo_descuento=motivo_descuento,
                    numero_pedidos_cliente=hist["numero_pedidos"],
                )
                ventas_service.registrar_compra_cliente(cliente_id, monto_total)
                pipeline_tracer.emitir(solicitud_id, "ventas", "Propuesta comercial generada", "completado")
            else:
                pipeline_tracer.emitir(solicitud_id, "ventas", "Sin cliente identificado, se omite propuesta", "completado")
        except Exception as e:
            log.warning("Cotizador IA (ventas) fallo, se omite propuesta comercial: %s", e)
            pipeline_tracer.emitir(solicitud_id, "ventas", f"Fallo: {e}", "error")

        pipeline_tracer.emitir(solicitud_id, "generadores", "Generando PDF, XLSX y modelo 3D", "en_progreso")
        work = Path(tempfile.mkdtemp(prefix="pm_rackbot_"))
        try:
            salidas = await asyncio.to_thread(
                pipeline.correr_pipeline, proyecto, work, descuento_pct, motivo_descuento,
            )
            log.info("Pipeline genero %d archivo(s)", len(salidas))

            salidas = [p for p in salidas if p.suffix.lower() != ".html"]

            persist = Path(tempfile.mkdtemp(prefix="pm_rackbot_persist_"))
            moved = []
            for p in salidas:
                try:
                    dst = persist / p.name
                    dst.write_bytes(p.read_bytes())
                    moved.append(dst)
                except Exception as e:
                    log.warning("no se pudo persistir %s: %s", p.name, e)
            resultado.archivos = moved

            # QA visual: best-effort, nunca bloquea la entrega (ver AskUserQuestion
            # respondida por el usuario -- un falso positivo no debe frenar una
            # venta real). Si detecta algo, solo queda registrado para revisión.
            try:
                # Solo las 2 mas diagnosticas (perspectiva general + detalle de
                # union) -- mandar las 5 hace que Groq rechace la llamada
                # ("Too many images provided, this model supports up to 3") y
                # ademas encarece de mas la revision de Claude sin aportar
                # senal extra (planta/frontal/lateral son vistas ortograficas,
                # menos utiles para juzgar defectos de ensamble que la
                # perspectiva + el acercamiento).
                nombres_diagnosticos = {"render_perspectiva.png", "render_modulo_detalle.png"}
                imagenes_render = [p for p in moved if p.name in nombres_diagnosticos]
                veredicto = await qa_visual_client.revisar_render(imagenes_render)
                if not veredicto["ok"]:
                    detalle = "; ".join(
                        f"[{d['severidad']}] {d['descripcion']}" for d in veredicto["defectos"]
                    )
                    log.warning("QA visual detecto defecto(s) en %s: %s", proyecto.get("clave"), detalle)
                    error_logger.registrar_error("qa_visual", f"Proyecto {proyecto.get('clave', '?')}: {detalle}")
                    pipeline_tracer.emitir(solicitud_id, "qa_visual", f"Defecto(s) detectado(s): {detalle}", "error")
                else:
                    pipeline_tracer.emitir(solicitud_id, "qa_visual", "Render revisado, sin defectos", "completado")
            except Exception as e:
                log.warning("QA visual fallo, se omite (no bloquea entrega): %s", e)

            if not moved and not resultado.link_visor_3d:
                extra = "No pude generar planos/renders (faltan dependencias en el servidor?)."
                resultado.validacion_texto = (resultado.validacion_texto or []) + [extra]
                resultado.avisos_validacion = list(resultado.avisos_validacion) + [extra]
            pipeline_tracer.emitir(solicitud_id, "generadores", f"{len(moved)} archivo(s) generado(s)", "completado")
        except Exception as e:
            log.exception("pipeline fallo")
            extra = f"Error generando planos/renders: {e}"
            resultado.validacion_texto = (resultado.validacion_texto or []) + [extra]
            resultado.avisos_validacion = list(resultado.avisos_validacion) + [extra]
            pipeline_tracer.emitir(solicitud_id, "generadores", f"Error generando entregables: {e}", "error")
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
    pipeline_tracer.emitir(solicitud_id, "usuario", "Respuesta entregada al cliente", "completado")
    return resultado


def limpiar_temporales(resultado: ResultadoProyectoPM) -> None:
    if resultado.archivos:
        try:
            shutil.rmtree(resultado.archivos[0].parent, ignore_errors=True)
        except Exception:
            pass
