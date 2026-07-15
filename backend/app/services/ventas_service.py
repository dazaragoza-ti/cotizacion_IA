"""Cotizador IA / Ventas — Cap. 7.12 del manual: el único dominio que
justifica un segundo agente, porque razona sobre negocio (descuentos,
historial de cliente), no sobre ingeniería de racks.

Todo lo que SÍ se puede calcular con aritmética simple vive aquí, en
Python determinista — el mismo criterio de "ingeniería antes que el
modelo" que ya usa validator_engine.py. Claude (ventas_client.py) solo
redacta el texto persuasivo a partir de estos números ya calculados;
nunca inventa el descuento ni el monto.
"""
from __future__ import annotations

import logging
import re
import unicodedata

from ..clients import supabase

log = logging.getLogger("ventas_service")

# Descuento por MONTO de este pedido en particular (incentiva volumen).
TRAMOS_DESCUENTO_PEDIDO = [
    (80_000.0, 0.10),
    (30_000.0, 0.05),
]
# Descuento por historial ACUMULADO del cliente antes de este pedido
# (incentiva lealtad). Son propuestas iniciales razonables -- pendientes
# de validar con el negocio, se ajustan cambiando esta tabla.
TRAMOS_DESCUENTO_HISTORIAL = [
    (150_000.0, 0.10),
    (50_000.0, 0.05),
]


def _normalizar_nombre(nombre: str) -> str:
    """minúsculas, sin acentos, espacios colapsados -- para que 'Bodega García'
    y 'bodega garcia' se reconozcan como el mismo cliente."""
    sin_acentos = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", sin_acentos.strip().lower())


def _normalizar_telefono(telefono: str | None) -> str | None:
    if not telefono:
        return None
    digitos = re.sub(r"\D", "", telefono)
    return digitos or None


def buscar_o_crear_cliente(nombre: str, telefono: str | None = None) -> str | None:
    """Encuentra el cliente existente (por teléfono si está disponible, si no
    por nombre normalizado) o crea uno nuevo. Devuelve su id, o None si no
    hay nombre con qué identificarlo."""
    if not nombre or not nombre.strip():
        return None

    nombre_norm = _normalizar_nombre(nombre)
    telefono_norm = _normalizar_telefono(telefono)

    try:
        if telefono_norm:
            existente = (supabase.table("clientes").select("id")
                         .eq("telefono", telefono_norm).limit(1).execute())
            if existente.data:
                return existente.data[0]["id"]

        existente = (supabase.table("clientes").select("id")
                     .eq("nombre_normalizado", nombre_norm).limit(1).execute())
        if existente.data:
            return existente.data[0]["id"]

        nuevo = supabase.table("clientes").insert({
            "nombre": nombre.strip(),
            "nombre_normalizado": nombre_norm,
            "telefono": telefono_norm,
        }).execute()
        return nuevo.data[0]["id"] if nuevo.data else None
    except Exception as e:
        log.warning("No se pudo buscar/crear cliente '%s': %s", nombre, e)
        return None


def historial_cliente(cliente_id: str) -> dict:
    """Historial ANTES de este pedido (para decidir su descuento)."""
    try:
        fila = (supabase.table("clientes")
                .select("monto_total_historico,numero_pedidos")
                .eq("id", cliente_id).limit(1).execute())
        if not fila.data:
            return {"monto_total_historico": 0.0, "numero_pedidos": 0}
        f = fila.data[0]
        return {
            "monto_total_historico": float(f.get("monto_total_historico") or 0),
            "numero_pedidos": int(f.get("numero_pedidos") or 0),
        }
    except Exception as e:
        log.warning("No se pudo leer historial del cliente %s: %s", cliente_id, e)
        return {"monto_total_historico": 0.0, "numero_pedidos": 0}


def registrar_compra_cliente(cliente_id: str, monto: float) -> None:
    """Suma este pedido al acumulado del cliente DESPUES de calcular su
    descuento (para que el pedido actual no se cuente a sí mismo)."""
    try:
        actual = historial_cliente(cliente_id)
        supabase.table("clientes").update({
            "monto_total_historico": actual["monto_total_historico"] + monto,
            "numero_pedidos": actual["numero_pedidos"] + 1,
        }).eq("id", cliente_id).execute()
    except Exception as e:
        log.warning("No se pudo registrar la compra del cliente %s: %s", cliente_id, e)


def _tramo(monto: float, tabla: list[tuple[float, float]]) -> float:
    for umbral, pct in tabla:
        if monto >= umbral:
            return pct
    return 0.0


def calcular_descuento(monto_pedido: float, monto_historico: float) -> tuple[float, str]:
    """Devuelve (porcentaje 0-1, motivo). Se aplica el MAYOR entre el tramo
    por volumen de este pedido y el tramo por historial del cliente -- no
    se acumulan, para no generar descuentos compuestos difíciles de
    justificar comercialmente."""
    pct_pedido = _tramo(monto_pedido, TRAMOS_DESCUENTO_PEDIDO)
    pct_historial = _tramo(monto_historico, TRAMOS_DESCUENTO_HISTORIAL)

    if pct_historial >= pct_pedido and pct_historial > 0:
        return pct_historial, f"cliente frecuente (${monto_historico:,.0f} MXN acumulados en pedidos anteriores)"
    if pct_pedido > 0:
        return pct_pedido, f"pedido de volumen (${monto_pedido:,.0f} MXN en esta cotización)"
    return 0.0, ""
