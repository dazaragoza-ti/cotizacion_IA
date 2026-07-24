"""Cliente de Claude para el QA visual del render 3D.

Tercer agente del sistema (Cap. 7.11/7.12 del manual: solo se justifica un
agente nuevo cuando razona sobre un dominio verdaderamente independiente —
igual que ventas_client.py). Este dominio es distinto tanto del proyectista
técnico (decide el layout) como del cotizador (redacta texto comercial):
mirar imágenes ya generadas y detectar defectos de ensamble visibles.

No genera el render (eso lo sigue haciendo modelo_3d.py, determinista) ni
corrige nada — solo emite un veredicto. Best-effort: nunca debe tumbar la
entrega al cliente si falla (ver proyecto_pm_service.py).

Ahorro de tokens (mismo patrón que ocr_service.py para fotos de Telegram):
1. Cada imagen se comprime/reescala antes de mandarla a Claude (cobra por
   píxeles, no por bytes del archivo).
2. Groq (rápido y barato) describe primero la geometría del render nuevo;
   esa descripción se agrega como contexto de texto para que Claude llegue
   ya orientado, sin tener que "leer" cada imagen desde cero.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path

from anthropic import AsyncAnthropic

from ... import config as _app_config  # noqa: F401 — garantiza que el .env ya esté cargado
from ...clients import groq_client
from ...services.ocr_service import comprimir_imagen
from ..tracing import anotar_run, traceable

log = logging.getLogger("qa_visual_client")
BASE = Path(__file__).parent.parent  # app/ai/

client = AsyncAnthropic()
# Sonnet con visión (no Opus): juzgar defectos de ensamble en renders no
# requiere Opus; Haiku también ve imágenes pero Sonnet acierta más en geometría.
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 1024

# ⚠️ Mismo modelo vigente que ocr_service.describir_imagen_groq — si
# empieza a fallar con "model not found", revisa el modelo vigente en
# https://console.groq.com/docs/vision y actualiza ambos a la vez.
MODELO_VISION_GROQ = "qwen/qwen3.6-27b"

SYSTEM_PROMPT = (BASE / "prompts" / "renderizador.md").read_text(encoding="utf-8")

# Kit de referencia ya armado correctamente ((-)_RACK_180X61X151, bucket
# 'modelos' de Supabase), renderizado una sola vez con matplotlib/trimesh
# (ver app/ai/generators/_draco_gltf_patch.py -- el .glb real viene
# comprimido con Draco, que trimesh no decodifica en lectura sin ese parche).
# Es un asset estatico: no se regenera por proyecto, solo se lee de disco.
_EJEMPLOS_DIR = BASE / "knowledge" / "ejemplos"
_REFERENCIA_PNGS = [
    _EJEMPLOS_DIR / "ejemplo_armado_referencia_perspectiva.png",
    _EJEMPLOS_DIR / "ejemplo_armado_referencia_detalle.png",
]
_referencia_cache: list[dict] | None = None  # comprimida una sola vez, se reusa entre llamadas

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean", "description": "true si no se detectó ningún defecto"},
        "defectos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "descripcion": {"type": "string"},
                    "severidad": {"type": "string", "enum": ["baja", "media", "alta"]},
                },
                "required": ["descripcion", "severidad"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["ok", "defectos"],
    "additionalProperties": False,
}


def _bloque_imagen(media_type: str, data: bytes) -> dict:
    b64 = base64.standard_b64encode(data).decode("utf-8")
    return {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}}


async def _bloques_referencia() -> list[dict]:
    global _referencia_cache
    if _referencia_cache is None:
        bloques = []
        for p in _REFERENCIA_PNGS:
            try:
                raw = p.read_bytes()
            except Exception as e:
                log.warning("no se pudo leer imagen de referencia %s: %s", p, e)
                continue
            media_type, data = await asyncio.to_thread(comprimir_imagen, raw)
            bloques.append(_bloque_imagen(media_type, data))
        _referencia_cache = bloques
    if not _referencia_cache:
        return []
    return [
        {"type": "text", "text": "Estas primeras imágenes son la REFERENCIA de un armado correcto:"},
        *_referencia_cache,
    ]


MAX_IMAGENES_GROQ = 3  # el modelo de visión de Groq rechaza la llamada por completo si se le mandan más


def _describir_geometria_groq(imagenes: list[tuple[str, bytes]]) -> str:
    """Describe con la visión de Groq (rápida y barata) cómo se unen las
    piezas del render nuevo, ANTES de que Claude lo vea — mismo patrón que
    ocr_service.describir_imagen_groq. Nunca lanza — si falla, Claude
    simplemente juzga con las imágenes, sin esta pista extra de texto."""
    imagenes = imagenes[:MAX_IMAGENES_GROQ]
    contenido: list[dict] = [{"type": "text", "text": (
        "Describe en detalle (hasta 8 líneas, en español) cómo se unen las piezas de "
        "este rack industrial: marcos, largueros, ménsulas, placas y cargadores. "
        "Menciona explícitamente si algo se ve encimado, flotando, faltante o mal "
        "alineado. Sé literal y descriptivo, no des un veredicto final."
    )}]
    for media_type, data in imagenes:
        b64 = base64.standard_b64encode(data).decode("ascii")
        contenido.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}})
    try:
        completion = groq_client.chat.completions.create(
            model=MODELO_VISION_GROQ,
            messages=[{"role": "user", "content": contenido}],
            temperature=0.2,
            max_completion_tokens=400,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:  # noqa: BLE001 — es una ayuda opcional, nunca debe romper el QA
        log.warning("descripción Groq para QA falló (modelo vigente puede haber cambiado): %s", e)
        return ""


@traceable(name="qa_visual.revisar_render", run_type="llm")
async def revisar_render(imagenes: list[Path]) -> dict:
    """Manda hasta las imágenes del render (ya generadas por modelo_3d.py) a
    Claude con visión y devuelve {"ok": bool, "defectos": [...]}.

    Nunca lanza — si algo falla (imagen ilegible, API caída, respuesta no
    parseable), devuelve ok=True para no bloquear la entrega; el llamador
    decide qué hacer con el resultado."""
    if not imagenes:
        return {"ok": True, "defectos": []}

    comprimidas: list[tuple[str, bytes]] = []
    for img in imagenes:
        try:
            raw = img.read_bytes()
        except Exception as e:
            log.warning("no se pudo leer %s para QA visual: %s", img, e)
            continue
        comprimidas.append(await asyncio.to_thread(comprimir_imagen, raw))
    if not comprimidas:
        return {"ok": True, "defectos": []}

    descripcion_groq = await asyncio.to_thread(_describir_geometria_groq, comprimidas)

    content: list[dict] = [
        *(await _bloques_referencia()),
        {"type": "text", "text": "Estas son las imágenes del render NUEVO a evaluar:"},
        *[_bloque_imagen(mt, data) for mt, data in comprimidas],
    ]
    if descripcion_groq:
        content.append({"type": "text", "text": f"Descripción previa (Groq) del render nuevo:\n{descripcion_groq}"})
    content.append({"type": "text", "text": "Compáralas contra la referencia y da tu veredicto."})

    try:
        message = await client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            output_config={"format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        )
        usage = getattr(message, "usage", None)
        if usage is not None:
            input_tokens = usage.input_tokens or 0
            output_tokens = usage.output_tokens or 0
            anotar_run(usage_metadata={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            })

        texto = next(b.text for b in message.content if b.type == "text")
        veredicto = json.loads(texto)
        return {"ok": bool(veredicto.get("ok", True)), "defectos": veredicto.get("defectos", [])}
    except Exception as e:
        log.warning("QA visual falló, se omite (no bloquea entrega): %s", e)
        return {"ok": True, "defectos": []}
