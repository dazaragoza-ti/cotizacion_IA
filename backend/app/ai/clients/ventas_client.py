"""Cliente de Claude para el agente de Ventas / Cotizador IA.

Segundo (y único otro) agente del sistema -- Cap. 7.12 del manual: se
justifica porque razona sobre un dominio distinto (negocio: descuentos,
tono comercial) del proyectista técnico (ingeniería de racks), con reglas
propias que nunca calcula el mismo LLM que diseña la estructura.

El descuento y los montos SIEMPRE llegan ya calculados por
ventas_service.py (determinista) -- este cliente solo redacta el texto
persuasivo a partir de esos números, nunca los inventa.
"""
from __future__ import annotations

import logging
from pathlib import Path

import anthropic
from anthropic import AsyncAnthropic

from ... import config as _app_config  # noqa: F401 — garantiza que el .env ya esté cargado

log = logging.getLogger("ventas_client")
BASE = Path(__file__).parent.parent  # app/ai/

client = AsyncAnthropic()
MODEL = "claude-opus-4-8"
MAX_TOKENS = 1024

SYSTEM_PROMPT = (BASE / "prompts" / "ventas.md").read_text(encoding="utf-8")


async def generar_propuesta_comercial(
    *,
    proyecto: dict,
    monto_total: float,
    descuento_pct: float,
    motivo_descuento: str,
    numero_pedidos_cliente: int,
) -> str:
    """Redacta la propuesta comercial breve que se manda por Telegram
    después de la cotización técnica. Nunca lanza — el llamador decide si
    omitir la propuesta cuando falla (ver proyecto_pm_service.py)."""
    contexto = (
        f"Proyecto: {proyecto.get('especificacion') or proyecto.get('clave') or 'rack industrial'}\n"
        f"Cliente: {proyecto.get('cliente') or 'Cliente'}\n"
        f"Monto cotizado: ${monto_total:,.2f} MXN\n"
        f"Pedidos previos de este cliente: {numero_pedidos_cliente}\n"
    )
    if descuento_pct > 0:
        contexto += f"Descuento aplicable: {descuento_pct * 100:.0f}% ({motivo_descuento})\n"
    else:
        contexto += "Sin descuento aplicable en este pedido.\n"

    message = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": contexto}],
    )
    return "".join(b.text for b in message.content if b.type == "text").strip()
