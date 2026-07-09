"""Cliente de Claude.

Arma el "cerebro" del especialista (instrucciones + archivos de conocimiento)
y genera el entregable a partir de la descripción, imágenes y PDFs que mande
el usuario por Telegram.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path

import anthropic
import httpx
from anthropic import AsyncAnthropic

from ... import config as _app_config  # noqa: F401 — garantiza que el .env del backend ya esté cargado
from .catalogo_pm_service import consultar_catalogo_pm

log = logging.getLogger("claude_client")
BASE = Path(__file__).parent

# Lee ANTHROPIC_API_KEY del entorno (ya cargado por `import config`).
client = AsyncAnthropic()

MODEL = "claude-opus-4-7"
MAX_TOKENS = 48000  # el render HTML + JSON + tablas pueden ser largos
MAX_REINTENTOS = 3

# Errores transitorios de red/servidor que vale la pena reintentar.
REINTENTABLES = (
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
    anthropic.RateLimitError,
    httpx.RemoteProtocolError,
    httpx.ReadError,
    httpx.ReadTimeout,
    httpx.ConnectError,
)


def _build_system() -> str:
    """Concatena las instrucciones (prompts/system.md) con todos los archivos
    de referencia que haya en knowledge/ (fichas técnicas, cuestionarios,
    ejemplos) — EXCEPTO catalogo_pm.json, que ahora se consulta en vivo desde
    Supabase en cada llamada (ver _bloque_catalogo_pm), para poder corregir
    precios/códigos sin tener que redesplegar el backend.

    El orden es determinista (alfabético) para que el prompt caching funcione
    y abarate las peticiones repetidas.
    """
    partes: list[str] = []

    system_file = BASE / "prompts" / "system.md"
    if system_file.exists():
        partes.append(system_file.read_text(encoding="utf-8"))

    knowledge_dir = BASE / "knowledge"
    if knowledge_dir.exists():
        # rglob: lee también subcarpetas (p. ej. knowledge/ejemplos/).
        for f in sorted(knowledge_dir.rglob("*")):
            if f.stem.lower() == "readme":
                continue
            if f.name == "catalogo_pm.json":
                continue  # se arma en vivo, ver _bloque_catalogo_pm()
            if f.is_file() and f.suffix.lower() in {".md", ".txt", ".csv", ".tsv", ".json", ".html"}:
                rel = f.relative_to(knowledge_dir)
                partes.append(
                    f"\n\n# Archivo de referencia: {rel}\n\n"
                    + f.read_text(encoding="utf-8")
                )

    return "\n".join(partes).strip()


# Se construye una vez al arrancar (instrucciones + fichas + ejemplos — rara
# vez cambian). El catálogo de precios NO va aquí, ver _bloque_catalogo_pm().
SYSTEM_PROMPT_BASE = _build_system()


def _bloque_catalogo_pm() -> str:
    """
    Arma el bloque del catálogo FRESCO en cada llamada, consultando Supabase
    (tabla catalogo_pm). Así, si corriges un precio o das de alta un código
    nuevo en Supabase, el bot lo usa desde el siguiente mensaje — sin reiniciar
    el proceso.
    """
    catalogo = consultar_catalogo_pm()
    return (
        "\n\n# Archivo de referencia: catalogo_pm.json (vivo desde Supabase — "
        "tabla catalogo_pm, consultada en cada mensaje)\n\n"
        + json.dumps(catalogo, indent=2, ensure_ascii=False)
    )


async def generar(
    descripcion: str,
    imagenes: list[tuple[str, bytes]],
    pdfs: list[bytes],
) -> tuple[str, int, int]:
    """Llama a Claude con la petición del usuario.

    - imagenes: lista de (media_type, bytes), p. ej. ("image/jpeg", b"...").
    - pdfs: lista de bytes de archivos PDF.

    Devuelve (texto_generado, input_tokens, output_tokens) — el uso real de
    tokens se necesita para guardarlo en disenos_racks/historial, no solo
    para logging.
    """
    content: list[dict] = []

    for media_type, data in imagenes:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64.standard_b64encode(data).decode("ascii"),
            },
        })

    for data in pdfs:
        content.append({
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": base64.standard_b64encode(data).decode("ascii"),
            },
        })

    content.append({
        "type": "text",
        "text": descripcion or "Genera el entregable según las instrucciones.",
    })

    # Streaming: la respuesta incluye un HTML completo (render 3D) y puede ser
    # larga, así que evitamos timeouts de la conexión. Reintentamos ante caídas.
    ultimo_error: Exception | None = None
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            async with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT_BASE,
                        "cache_control": {"type": "ephemeral"},  # cachea el cerebro (instrucciones+fichas+ejemplos)
                    },
                    {
                        "type": "text",
                        "text": _bloque_catalogo_pm(),
                        "cache_control": {"type": "ephemeral"},  # catálogo vivo, se recalcula cada llamada
                    },
                ],
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},  # baja a "medium" para gastar menos
                messages=[{"role": "user", "content": content}],
            ) as stream:
                message = await stream.get_final_message()
            texto = "".join(b.text for b in message.content if b.type == "text")
            usage = message.usage
            input_tokens = (usage.input_tokens or 0) if usage else 0
            output_tokens = (usage.output_tokens or 0) if usage else 0
            # Los tokens leídos/creados de caché también cuentan como "input"
            # real cobrado — se suman para que el número refleje el costo total.
            if usage:
                input_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
                input_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
            return texto, input_tokens, output_tokens
        except REINTENTABLES as e:
            ultimo_error = e
            log.warning("Reintento %d/%d tras error transitorio: %s",
                        intento, MAX_REINTENTOS, type(e).__name__)
            if intento < MAX_REINTENTOS:
                await asyncio.sleep(2 * intento)

    raise ultimo_error  # se agotaron los reintentos
