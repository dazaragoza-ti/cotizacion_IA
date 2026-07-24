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
from ...services.catalogo_pm_service import consultar_catalogo_pm
from ..tracing import anotar_run, traceable

log = logging.getLogger("claude_client")
# app/ai/clients/claude_client.py -> app/ai/ (donde viven prompts/ y knowledge/ como carpetas hermanas)
BASE = Path(__file__).parent.parent

# Lee ANTHROPIC_API_KEY del entorno (ya cargado por `import config`).
client = AsyncAnthropic()

MODEL = "claude-opus-4-7"
MAX_TOKENS = 48000  # el render HTML + JSON + tablas pueden ser largos
MAX_REINTENTOS = 3

# Ahorro de tokens: el system estable solo lleva 1–2 JSON dorados (formato).
# Fichas `tecnico/*` van por RAG (`tipo=manual`) tras sync — no se embeben aquí
# salvo EMBED_FICHAS_EN_PROMPT=1 (fallback offline / sin chunks).
# Cuestionarios, HTML y dumps grandes quedan fuera.
# Dorados: SOLO disco/git (`knowledge/ejemplos/`); NUNCA se indexan en Supabase.
_MAX_EJEMPLOS_DORADOS = 2
_SUFIJOS_FICHA = {".md", ".txt"}
_SUFIJOS_DORADO = {".json"}

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


def _embeber_fichas_en_prompt() -> bool:
    """True solo si se fuerza fallback (sin RAG) vía env."""
    import os
    return os.getenv("EMBED_FICHAS_EN_PROMPT", "").strip().lower() in ("1", "true", "yes")


def _archivos_knowledge_whitelist(knowledge_dir: Path) -> list[Path]:
    """Whitelist determinista (orden alfabético) para prompt caching estable.

    Incluye por defecto:
    - hasta `_MAX_EJEMPLOS_DORADOS` JSON en `ejemplos/` (dorados, solo disco)

    Fichas `tecnico/*`: NO por defecto (van por RAG `tipo=manual`).
    Con `EMBED_FICHAS_EN_PROMPT=1` se re-embeben (híbrido de emergencia).

    Excluye: HTML, cuestionarios, catalogo_pm.json, README, PDF/PNG, CSV grandes.
    """
    elegidos: list[Path] = []

    if _embeber_fichas_en_prompt():
        tecnico = knowledge_dir / "tecnico"
        if tecnico.is_dir():
            for f in sorted(tecnico.iterdir()):
                if f.is_file() and f.suffix.lower() in _SUFIJOS_FICHA and f.stem.lower() != "readme":
                    elegidos.append(f)

    ejemplos = knowledge_dir / "ejemplos"
    if ejemplos.is_dir():
        dorados = [
            f for f in sorted(ejemplos.iterdir())
            if f.is_file()
            and f.suffix.lower() in _SUFIJOS_DORADO
            and f.stem.lower() != "readme"
            and f.name != "catalogo_pm.json"
        ]
        elegidos.extend(dorados[:_MAX_EJEMPLOS_DORADOS])

    return elegidos


def _build_system() -> str:
    """Instrucciones (prompts/system.md) + whitelist corta de knowledge/.

    El catálogo vivo NO va aquí (ver `_bloque_catalogo_pm`): debe quedar en un
    bloque system separado para que el prompt caching del cerebro no se invalide
    cuando filtramos o actualizamos precios.
    """
    partes: list[str] = []

    system_file = BASE / "prompts" / "system.md"
    if system_file.exists():
        partes.append(system_file.read_text(encoding="utf-8"))

    knowledge_dir = BASE / "knowledge"
    if knowledge_dir.exists():
        for f in _archivos_knowledge_whitelist(knowledge_dir):
            rel = f.relative_to(knowledge_dir)
            partes.append(
                f"\n\n# Archivo de referencia: {rel}\n\n"
                + f.read_text(encoding="utf-8")
            )

    return "\n".join(partes).strip()


# Se construye una vez al arrancar (instrucciones + fichas + 1–2 dorados).
# Estable → cacheable. El catálogo vivo va en otro bloque.
SYSTEM_PROMPT_BASE = _build_system()


def _bloque_catalogo_pm(catalogo: list[dict] | None = None) -> str:
    """
    Bloque del catálogo FRESCO (Supabase o subset ya filtrado por familia).

    Separado de SYSTEM_PROMPT_BASE a propósito: el cerebro se cachea; este
    bloque cambia por familia / precios y tiene su propio cache_control.
    """
    if catalogo is None:
        catalogo = consultar_catalogo_pm()
    # Sin indent: menos tokens que indent=2; el modelo parsea JSON compacto igual.
    return (
        "\n\n# Archivo de referencia: catalogo_pm.json (vivo desde Supabase — "
        "tabla catalogo_pm; puede venir filtrado por familia+comunes)\n\n"
        + json.dumps(catalogo, ensure_ascii=False, separators=(",", ":"))
    )


@traceable(name="proyectista.generar", run_type="llm")
async def generar(
    descripcion: str,
    imagenes: list[tuple[str, bytes]],
    pdfs: list[bytes],
    catalogo_pm: list[dict] | None = None,
) -> tuple[str, int, int]:
    """Llama a Claude con la petición del usuario.

    - imagenes: lista de (media_type, bytes), p. ej. ("image/jpeg", b"...").
    - pdfs: lista de bytes de archivos PDF.
    - catalogo_pm: subset opcional (familia+comunes). Si es None, consulta el
      catálogo completo (fallback).

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
            # SYSTEM_PROMPT_BASE es estable (cache hit entre llamadas).
            # bloque_catalogo es vivo/filtrado — bloque aparte para no romper
            # el cache del cerebro cuando cambia la familia o los precios.
            bloque_catalogo = _bloque_catalogo_pm(catalogo_pm)
            async with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT_BASE,
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": bloque_catalogo,
                        "cache_control": {"type": "ephemeral"},
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
            # Sprint 2, Fase 5: mapea el uso real a usage_metadata para que
            # LangSmith calcule el costo, y adjunta el system prompt real
            # (antes la traza solo mostraba el mensaje del usuario).
            anotar_run(
                usage_metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                system_prompt=SYSTEM_PROMPT_BASE + chr(10)*2 + bloque_catalogo,
            )
            return texto, input_tokens, output_tokens
        except REINTENTABLES as e:
            ultimo_error = e
            log.warning("Reintento %d/%d tras error transitorio: %s",
                        intento, MAX_REINTENTOS, type(e).__name__)
            if intento < MAX_REINTENTOS:
                await asyncio.sleep(2 * intento)

    raise ultimo_error  # se agotaron los reintentos
