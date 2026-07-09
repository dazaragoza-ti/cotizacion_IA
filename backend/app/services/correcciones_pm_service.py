"""
Correcciones del proyectista PM (reutiliza la tabla correcciones_armado,
extendida con columnas para guardar el contexto completo: proyecto
antes/despues, clave, usuario, y de donde vino la correccion -origen-).

Dos origenes, en la misma tabla:

- manual: el cliente/vendedor manda un ajuste sobre un proyecto YA
  generado, detectado porque el nuevo proyecto conserva la misma clave
  que el anterior de esa sesion. Es bitacora real de negocio.

- automatico: validador.py encontro errores/advertencias en un proyecto
  que genero Claude, sin que nadie tenga que escribir nada. Es control
  de calidad del modelo.
"""
from __future__ import annotations

import logging

from ..clients import supabase
from ..ai.rag.vector_store import vector_store
from ..ai.rag.chunkers import correccion_to_document

log = logging.getLogger("pm_rackbot.correcciones")

TABLA = "correcciones_armado"


def _registrar(
    session_id: str,
    tg_user_id: int | None,
    tipo: str | None,
    clave: str | None,
    descripcion: str,
    proyecto_antes: dict | None,
    proyecto_despues: dict | None,
    origen: str,
) -> int | None:
    try:
        existente = (
            supabase.table(TABLA).select("id, veces_repetida")
            .eq("descripcion_error", descripcion)
            .eq("proyecto_clave", clave)
            .eq("origen", origen)
            .limit(1)
            .execute()
        )
        if existente.data:
            fila = existente.data[0]
            veces_nuevo = fila["veces_repetida"] + 1
            supabase.table(TABLA).update({
                "veces_repetida": veces_nuevo,
                "proyecto_json_despues": proyecto_despues,
            }).eq("id", fila["id"]).execute()

            _indexar_en_vivo(
                correccion_id=fila["id"], tipo_rack=tipo, pieza_afectada=None,
                descripcion_error=descripcion, instruccion_correctiva=descripcion,
                veces_repetida=veces_nuevo, proyecto_clave=clave, origen=origen,
            )
            return fila["id"]

        resultado = supabase.table(TABLA).insert({
            "session_id": session_id,
            "tg_user_id": tg_user_id,
            "tipo_rack": tipo,
            "proyecto_clave": clave,
            "descripcion_error": descripcion,
            "instruccion_correctiva": descripcion,
            "proyecto_json_antes": proyecto_antes,
            "proyecto_json_despues": proyecto_despues,
            "veces_repetida": 1,
            "origen": origen,
        }).execute()

        if resultado.data:
            nueva_id = resultado.data[0]["id"]
            _indexar_en_vivo(
                correccion_id=nueva_id, tipo_rack=tipo, pieza_afectada=None,
                descripcion_error=descripcion, instruccion_correctiva=descripcion,
                veces_repetida=1, proyecto_clave=clave, origen=origen,
            )
            return nueva_id
        return None
    except Exception as e:
        log.exception("_registrar(origen=%s) fallo: %s", origen, e)
        return None


def _indexar_en_vivo(
    correccion_id: int,
    tipo_rack: str | None,
    pieza_afectada: str | None,
    descripcion_error: str,
    instruccion_correctiva: str,
    veces_repetida: int,
    proyecto_clave: str | None,
    origen: str,
) -> None:
    try:
        documento = correccion_to_document({
            "tipo_rack": tipo_rack,
            "pieza_afectada": pieza_afectada,
            "descripcion_error": descripcion_error,
            "instruccion_correctiva": instruccion_correctiva,
            "veces_repetida": veces_repetida,
            "proyecto_clave": proyecto_clave,
            "origen": origen,
        })
        vector_store.upsert(
            tipo="correccion",
            fuente="correcciones_armado",
            referencia_id=str(correccion_id),
            contenido=documento,
            metadata={
                "tipo_rack": tipo_rack,
                "pieza_afectada": pieza_afectada,
                "proyecto_clave": proyecto_clave,
                "veces_repetida": veces_repetida,
                "origen": origen,
            },
        )
    except Exception as e:
        log.warning("No se pudo indexar la correccion %s en vivo: %s", correccion_id, e)


def registrar_correccion(
    session_id: str,
    tg_user_id: int | None,
    tipo: str | None,
    clave: str | None,
    comentario_cliente: str,
    proyecto_antes: dict,
    proyecto_despues: dict,
) -> int | None:
    return _registrar(
        session_id=session_id, tg_user_id=tg_user_id, tipo=tipo, clave=clave,
        descripcion=comentario_cliente, proyecto_antes=proyecto_antes,
        proyecto_despues=proyecto_despues, origen="manual",
    )


def registrar_correccion_automatica(
    session_id: str,
    tg_user_id: int | None,
    tipo: str | None,
    clave: str | None,
    detalle_validacion: str,
    proyecto: dict,
) -> int | None:
    return _registrar(
        session_id=session_id, tg_user_id=tg_user_id, tipo=tipo, clave=clave,
        descripcion=detalle_validacion, proyecto_antes=None,
        proyecto_despues=proyecto, origen="automatico",
    )


def es_correccion(proyecto_anterior: dict | None, proyecto_nuevo: dict | None) -> bool:
    if not proyecto_anterior or not proyecto_nuevo:
        return False
    clave_antes = (proyecto_anterior.get("clave") or "").strip()
    clave_despues = (proyecto_nuevo.get("clave") or "").strip()
    return bool(clave_antes) and clave_antes == clave_despues
