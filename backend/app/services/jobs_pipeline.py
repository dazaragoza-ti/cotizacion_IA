"""Cola simple de jobs del pipeline (migración 0014).

Best-effort: si la tabla `jobs_pipeline` no existe en remoto, no bloquea.
Uso típico: enqueue al iniciar generación; un worker futuro puede claim/finish.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from ..clients import supabase_service

log = logging.getLogger("jobs_pipeline")

TABLA = "jobs_pipeline"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def enqueue(
    tipo: str,
    *,
    session_id: str | None = None,
    tg_user_id: int | None = None,
    payload: dict[str, Any] | None = None,
) -> str | None:
    """Inserta un job `pending`. Devuelve id o None si Supabase/tabla falla."""
    job_id = str(uuid4())
    fila = {
        "id": job_id,
        "tipo": tipo or "generar_proyecto",
        "session_id": session_id,
        "tg_user_id": tg_user_id,
        "payload": payload or {},
        "estado": "pending",
        "created_at": _now(),
    }
    try:
        supabase_service.table(TABLA).insert(fila).execute()
        return job_id
    except Exception as e:  # noqa: BLE001
        log.warning("jobs_pipeline.enqueue no-op (%s): %s", tipo, e)
        return None


def mark_running(job_id: str | None) -> None:
    if not job_id:
        return
    try:
        supabase_service.table(TABLA).update({
            "estado": "running",
            "started_at": _now(),
        }).eq("id", job_id).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("jobs_pipeline.mark_running fallo: %s", e)


def mark_done(job_id: str | None, *, error: str | None = None) -> None:
    if not job_id:
        return
    estado = "error" if error else "done"
    try:
        supabase_service.table(TABLA).update({
            "estado": estado,
            "error": error,
            "finished_at": _now(),
        }).eq("id", job_id).execute()
    except Exception as e:  # noqa: BLE001
        log.warning("jobs_pipeline.mark_done fallo: %s", e)
