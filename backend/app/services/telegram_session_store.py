"""Persistencia de cuestionario + buffers de Telegram en Supabase.

Sin Redis en el stack: tabla `telegram_sesiones` (migración 0012).
TTL por defecto 24 h. `/cancelar` y fin de generación borran la fila.
Best-effort: si Supabase falla, el caller puede seguir con memoria local.
"""
from __future__ import annotations

import base64
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from ..clients import supabase_service

log = logging.getLogger("telegram_session_store")

TABLA = "telegram_sesiones"
TTL_HORAS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _expires() -> str:
    return (_now() + timedelta(hours=TTL_HORAS)).isoformat()


def _encode_buffers(buf: dict) -> dict:
    """Serializa adjuntos binarios a base64 para jsonb."""
    imagenes = []
    for item in buf.get("imagenes") or []:
        if isinstance(item, (list, tuple)) and len(item) == 2:
            mime, data = item
            imagenes.append({
                "mime": mime,
                "b64": base64.b64encode(data).decode("ascii"),
            })
    pdfs = [
        base64.b64encode(p).decode("ascii")
        for p in (buf.get("pdfs") or [])
        if isinstance(p, (bytes, bytearray))
    ]
    return {
        "imagenes": imagenes,
        "pdfs": pdfs,
        "capciones": list(buf.get("capciones") or []),
    }


def _decode_buffers(raw: dict | None) -> dict:
    raw = raw or {}
    imagenes: list[tuple[str, bytes]] = []
    for item in raw.get("imagenes") or []:
        try:
            mime = item.get("mime") or "image/jpeg"
            data = base64.b64decode(item.get("b64") or "")
            if data:
                imagenes.append((mime, data))
        except Exception:  # noqa: BLE001
            continue
    pdfs: list[bytes] = []
    for b64 in raw.get("pdfs") or []:
        try:
            data = base64.b64decode(b64)
            if data:
                pdfs.append(data)
        except Exception:  # noqa: BLE001
            continue
    return {
        "imagenes": imagenes,
        "pdfs": pdfs,
        "capciones": list(raw.get("capciones") or []),
    }


def estado_a_dict(est: Any) -> dict:
    return {
        "texto_acumulado": getattr(est, "texto_acumulado", "") or "",
        "campos_recolectados": sorted(getattr(est, "campos_recolectados", set()) or []),
        "tipo_rack": getattr(est, "tipo_rack", None),
        "modo_guiado": bool(getattr(est, "modo_guiado", False)),
        "siguiente_pregunta_idx": int(getattr(est, "siguiente_pregunta_idx", 0) or 0),
    }


def aplicar_estado_dict(est: Any, data: dict | None) -> None:
    if not data:
        return
    est.texto_acumulado = data.get("texto_acumulado") or ""
    campos = data.get("campos_recolectados") or []
    est.campos_recolectados = set(campos) if isinstance(campos, list) else set()
    est.tipo_rack = data.get("tipo_rack")
    est.modo_guiado = bool(data.get("modo_guiado", False))
    est.siguiente_pregunta_idx = int(data.get("siguiente_pregunta_idx") or 0)


def cargar(chat_id: str) -> tuple[dict | None, dict | None]:
    """Devuelve (estado_cuestionario, buffers) o (None, None) si no hay fila / expiró."""
    try:
        res = (
            supabase_service.table(TABLA)
            .select("estado_cuestionario,buffers,expires_at")
            .eq("chat_id", chat_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None, None
        fila = res.data[0]
        exp = fila.get("expires_at")
        if exp:
            try:
                exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                if exp_dt < _now():
                    borrar(chat_id)
                    return None, None
            except Exception:  # noqa: BLE001
                pass
        return fila.get("estado_cuestionario") or {}, _decode_buffers(fila.get("buffers"))
    except Exception as e:  # noqa: BLE001
        log.warning("telegram_session_store.cargar fallo: %s", e)
        return None, None


def guardar(
    chat_id: str,
    *,
    user_id: int | None,
    estado: dict | None,
    buffers: dict | None,
) -> None:
    payload = {
        "chat_id": chat_id,
        "user_id": user_id,
        "estado_cuestionario": estado or {},
        "buffers": _encode_buffers(buffers or {"imagenes": [], "pdfs": [], "capciones": []}),
        "updated_at": _now().isoformat(),
        "expires_at": _expires(),
    }
    try:
        supabase_service.table(TABLA).upsert(payload).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("telegram_session_store.guardar fallo: %s", e)


def borrar(chat_id: str) -> None:
    try:
        supabase_service.table(TABLA).delete().eq("chat_id", chat_id).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("telegram_session_store.borrar fallo: %s", e)


def limpiar_expiradas() -> int:
    """Best-effort; útil si se llama desde un job. Devuelve filas borradas (aprox)."""
    try:
        res = (
            supabase_service.table(TABLA)
            .delete()
            .lt("expires_at", _now().isoformat())
            .execute()
        )
        return len(res.data or [])
    except Exception as e:  # noqa: BLE001
        log.warning("telegram_session_store.limpiar_expiradas fallo: %s", e)
        return 0
