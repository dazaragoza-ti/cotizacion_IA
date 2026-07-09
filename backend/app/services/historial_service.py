"""Persistencia del histórico de proyectos del proyectista PM (rack-bot).

Adaptado del historial.py original de rack-bot: misma API pública
(registrar, listar, por_id, resumen_por_tipo, resumen_por_usuario,
archivos_de), pero usando los clientes de Supabase que ya existen en
app.clients en vez de crear uno propio — así comparte credenciales/pool
con el resto del backend.

Tabla: proyectos_pm_historial (ver sql_historial_pm.sql).
Archivos: bucket 'cotizaciones', carpeta historial_rackbot/<id>/.

Diseñado para fallar suave: si algo aquí truena, NO debe interrumpir
la respuesta al usuario en Telegram.
"""
from __future__ import annotations

import logging
from pathlib import Path

from ..clients import supabase, supabase_service

log = logging.getLogger("pm_rackbot.historial")

TABLA = "proyectos_pm_historial"
BUCKET = "cotizaciones"
CARPETA_BASE = "historial_rackbot"

_cliente_storage = supabase_service if supabase_service else supabase


_TIPO_KEYS = [
    ("cantilever",  "cantilever"),
    ("mezzanine",   "mezzanine"),
    ("mezanine",    "mezzanine"),
    ("entrepiso",   "mezzanine"),
    ("archivo",     "archivo"),
    ("leford",      "archivo"),
    ("locker",      "mueble"),
    ("gabinete",    "mueble"),
    ("armario",     "mueble"),
    ("mueble",      "mueble"),
    ("estanteria",  "estanteria"),
    ("estantería",  "estanteria"),
    ("selectivo",   "selectivo"),
    ("rack",        "selectivo"),
]


def detectar_tipo(proyecto_json: dict | None, texto_descripcion: str,
                  respuesta_texto: str) -> str:
    if proyecto_json:
        layout = proyecto_json.get("layout") or {}
        for campo in (layout.get("tipo"), proyecto_json.get("especificacion")):
            if campo:
                low = str(campo).lower()
                for k, lab in _TIPO_KEYS:
                    if k in low:
                        return lab
    for fuente in (respuesta_texto or "", texto_descripcion or ""):
        low = fuente.lower()
        for k, lab in _TIPO_KEYS:
            if k in low:
                return lab
    return "otro"


def _monto_total(proyecto_json: dict | None) -> float | None:
    if not proyecto_json:
        return None
    materiales = proyecto_json.get("materiales") or []
    total = 0.0
    contado = 0
    for m in materiales:
        pzas = m.get("pzas") or 0
        precio = m.get("precio") or 0
        try:
            total += float(pzas) * float(precio)
            contado += 1
        except (TypeError, ValueError):
            continue
    return round(total, 2) if contado > 0 else None


def _subir_archivo(row_id: int, path: Path) -> dict | None:
    try:
        contenido = path.read_bytes()
        destino = f"{CARPETA_BASE}/{row_id}/{path.name}"
        _cliente_storage.storage.from_(BUCKET).upload(
            path=destino,
            file=contenido,
            file_options={"cache-control": "3600", "upsert": "true"},
        )
        url = _cliente_storage.storage.from_(BUCKET).get_public_url(destino)
        return {"name": path.name, "url": url, "size": len(contenido)}
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo subir %s a Storage: %s", path, e)
        return None


def registrar(
    tg_user_id: int | None,
    tg_username: str | None,
    tg_full_name: str | None,
    descripcion: str,
    respuesta_texto: str,
    proyecto_json: dict | None,
    render_html: str | None,
    archivos_pipeline: list[Path] | None,
    n_imagenes: int = 0,
    n_pdfs: int = 0,
    error: str | None = None,
    session_id: str | None = None,
) -> int | None:
    try:
        tipo = detectar_tipo(proyecto_json, descripcion, respuesta_texto)
        cliente = (proyecto_json or {}).get("cliente") or ""
        clave = (proyecto_json or {}).get("clave") or ""
        monto = _monto_total(proyecto_json)
        num_modulos = None
        if proyecto_json:
            lay = proyecto_json.get("layout") or {}
            mx = lay.get("modulos_x") or 0
            my = lay.get("modulos_y") or 0
            if mx and my:
                num_modulos = int(mx) * int(my)
        estado = "error" if error else (
            "ok" if (proyecto_json and respuesta_texto) else "parcial"
        )

        payload = {
            "tg_user_id": tg_user_id,
            "tg_username": tg_username,
            "tg_full_name": tg_full_name,
            "session_id": session_id,
            "descripcion": descripcion or "",
            "respuesta_texto": respuesta_texto or "",
            "tipo": tipo,
            "cliente": cliente,
            "clave": clave,
            "monto_total": monto,
            "num_modulos": num_modulos,
            "estado": estado,
            "n_imagenes": n_imagenes,
            "n_pdfs": n_pdfs,
            "respuesta_len": len(respuesta_texto or ""),
            "error_msg": error,
            "proyecto_json": proyecto_json,
            "render_html_claude": render_html,
            "archivos": [],
        }
        resultado = supabase.table(TABLA).insert(payload).execute()
        if not resultado.data:
            raise RuntimeError("Insert a proyectos_pm_historial no devolvió fila.")
        row_id = resultado.data[0]["id"]

        archivos_meta = []
        for p in archivos_pipeline or []:
            meta = _subir_archivo(row_id, Path(p))
            if meta:
                archivos_meta.append(meta)

        if archivos_meta:
            supabase.table(TABLA).update({"archivos": archivos_meta}).eq("id", row_id).execute()

        return row_id
    except Exception as e:  # noqa: BLE001
        log.exception("registrar() falló: %s", e)
        return None


def listar(limit: int = 100) -> list[dict]:
    try:
        res = supabase.table(TABLA).select("*").order("ts", desc=True).limit(limit).execute()
        return res.data or []
    except Exception as e:  # noqa: BLE001
        log.exception("listar() falló: %s", e)
        return []


def por_id(row_id: int) -> dict | None:
    try:
        res = supabase.table(TABLA).select("*").eq("id", row_id).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:  # noqa: BLE001
        log.exception("por_id() falló: %s", e)
        return None


def resumen_por_tipo() -> list[dict]:
    filas = listar(limit=10000)
    agregados: dict[str, dict] = {}
    for r in filas:
        t = r.get("tipo") or "otro"
        entry = agregados.setdefault(t, {"tipo": t, "n": 0, "monto": 0.0})
        entry["n"] += 1
        entry["monto"] += r.get("monto_total") or 0
    return sorted(agregados.values(), key=lambda x: -x["n"])


def resumen_por_usuario() -> list[dict]:
    filas = listar(limit=10000)
    agregados: dict = {}
    for r in filas:
        uid = r.get("tg_user_id")
        entry = agregados.setdefault(uid, {
            "tg_user_id": uid,
            "tg_username": r.get("tg_username"),
            "tg_full_name": r.get("tg_full_name"),
            "n": 0, "monto": 0.0, "ultimo": r.get("ts"),
        })
        entry["n"] += 1
        entry["monto"] += r.get("monto_total") or 0
        if r.get("ts") and (not entry["ultimo"] or r["ts"] > entry["ultimo"]):
            entry["ultimo"] = r["ts"]
    return sorted(agregados.values(), key=lambda x: -x["n"])


def archivos_de(row_id: int) -> list[dict]:
    row = por_id(row_id)
    if not row:
        return []
    return row.get("archivos") or []


def ultimo_proyecto_de_sesion(session_id: str) -> dict | None:
    """
    Recupera el último proyecto generado con éxito para esta sesión de
    Telegram (con proyecto_json no nulo). Se usa para: (1) darle a Claude el
    diseño anterior como contexto cuando el cliente pide un ajuste, y
    (2) detectar si el nuevo mensaje es una corrección sobre ese proyecto.
    """
    try:
        res = (
            supabase.table(TABLA).select("*")
            .eq("session_id", session_id)
            .not_.is_("proyecto_json", "null")
            .order("ts", desc=True)
            .limit(1)
            .execute()
        )
        return res.data[0] if res.data else None
    except Exception as e:  # noqa: BLE001
        log.exception("ultimo_proyecto_de_sesion() falló: %s", e)
        return None
