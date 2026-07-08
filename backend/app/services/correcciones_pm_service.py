"""
Correcciones del proyectista PM — reutiliza la tabla `correcciones_armado`
(la misma que ya tenías del agente rápido), extendida con columnas para
guardar el contexto completo: proyecto antes/después, clave, usuario, y de
dónde vino la corrección (`origen`).

Dos orígenes, en la misma tabla:

- **manual**: el cliente/vendedor manda un ajuste sobre un proyecto YA
  generado (ej. "el precio de la cabecera está mal", "sube el segundo nivel
  20cm"), detectado porque el nuevo proyecto conserva la misma `clave` que
  el anterior de esa sesión. Es bitácora real de negocio.

- **automatico**: `validador.py` encontró errores/advertencias en un
  proyecto que generó Claude, sin que nadie tenga que escribir nada. Es
  control de calidad del modelo — mide qué tan seguido se equivoca, no lo
  que el cliente pide cambiar.
"""
from __future__ import annotations

import logging

from ..clients import supabase

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
    """
    Guarda una corrección (manual o automática). Si ya existe una con la
    misma descripción + clave + origen, solo incrementa veces_repetida en
    vez de duplicar la fila (mismo patrón que usaba el agente rápido).
    """
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
            supabase.table(TABLA).update({
                "veces_repetida": fila["veces_repetida"] + 1,
                "proyecto_json_despues": proyecto_despues,
            }).eq("id", fila["id"]).execute()
            return fila["id"]

        resultado = supabase.table(TABLA).insert({
            "session_id": session_id,
            "tg_user_id": tg_user_id,
            "tipo_rack": tipo,
            "proyecto_clave": clave,
            "descripcion_error": descripcion,
            "instruccion_correctiva": descripcion,  # de momento, tal cual; se puede reescribir después
            "proyecto_json_antes": proyecto_antes,
            "proyecto_json_despues": proyecto_despues,
            "veces_repetida": 1,
            "origen": origen,
        }).execute()
        return resultado.data[0]["id"] if resultado.data else None
    except Exception as e:  # noqa: BLE001 — no debe romper la respuesta al cliente
        log.exception("_registrar(origen=%s) falló: %s", origen, e)
        return None


def registrar_correccion(
    session_id: str,
    tg_user_id: int | None,
    tipo: str | None,
    clave: str | None,
    comentario_cliente: str,
    proyecto_antes: dict,
    proyecto_despues: dict,
) -> int | None:
    """Opción A: ajuste manual pedido por el cliente/vendedor sobre un proyecto ya generado."""
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
    """
    Opción B: lo que validador.py marcó (errores y/o advertencias) en un
    proyecto recién generado, sin intervención humana. No hay "antes" —
    es una sola fotografía del proyecto con lo que falló.
    """
    return _registrar(
        session_id=session_id, tg_user_id=tg_user_id, tipo=tipo, clave=clave,
        descripcion=detalle_validacion, proyecto_antes=None,
        proyecto_despues=proyecto, origen="automatico",
    )


def es_correccion(proyecto_anterior: dict | None, proyecto_nuevo: dict | None) -> bool:
    """
    Señal simple y determinista: si el proyecto nuevo conserva la misma
    `clave` que el anterior, es porque Claude decidió que era un ajuste al
    mismo proyecto (así lo indican las instrucciones del sistema), no uno nuevo.
    """
    if not proyecto_anterior or not proyecto_nuevo:
        return False
    clave_antes = (proyecto_anterior.get("clave") or "").strip()
    clave_despues = (proyecto_nuevo.get("clave") or "").strip()
    return bool(clave_antes) and clave_antes == clave_despues
