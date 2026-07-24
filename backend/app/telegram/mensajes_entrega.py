"""Copia y estructura del mensaje final de entrega por Telegram."""
from __future__ import annotations

import html
from pathlib import Path

from ..ai.pipelines.utils import trocear

# Límite seguro bajo el tope de Telegram (4096).
_LIMITE = 4000

_ETIQUETAS_RENDER = {
    "render_perspectiva.png": "Render perspectiva",
    "render_planta.png": "Render planta",
    "render_frontal.png": "Render frontal",
    "render_lateral.png": "Render lateral",
    "render_modulo_detalle.png": "Render detalle de módulo",
}


def _esc(valor: object) -> str:
    return html.escape(str(valor), quote=False) if valor is not None else ""


def _tipo_proyecto(proyecto: dict | None) -> str | None:
    if not proyecto:
        return None
    tipo = proyecto.get("especificacion") or (proyecto.get("layout") or {}).get("tipo")
    if not tipo:
        return None
    return str(tipo).replace("_", " ").strip().title()


def etiqueta_archivo(path: Path) -> str:
    nombre = path.name
    low = nombre.lower()
    if low in _ETIQUETAS_RENDER:
        return _ETIQUETAS_RENDER[low]
    if low.startswith("planos_") and low.endswith(".pdf"):
        return "Planos PDF"
    if low.startswith("cotizacion_") and low.endswith(".pdf"):
        return "Cotización PDF"
    if low.startswith("despiece_") and low.endswith(".xlsx"):
        return "Despiece / cotización XLSX"
    if low.endswith(".glb"):
        return "Modelo 3D (.glb)"
    if low.endswith(".dae"):
        return "Modelo 3D (.dae)"
    if low.endswith(".png"):
        return f"Render ({nombre})"
    if low.endswith(".pdf"):
        return f"PDF ({nombre})"
    if low.endswith(".xlsx"):
        return f"Excel ({nombre})"
    return nombre


def _lista_entregables(archivos: list[Path]) -> list[str]:
    """Agrupa renders y lista el resto con etiqueta legible (mismo orden de envío)."""
    if not archivos:
        return []
    archivos = ordenar_archivos_entrega(archivos)
    items: list[str] = []
    n_renders = sum(1 for p in archivos if p.suffix.lower() == ".png")
    vistos_png = False
    for p in archivos:
        if p.suffix.lower() == ".png":
            if not vistos_png:
                items.append(
                    f"Renders ({n_renders})" if n_renders > 1 else etiqueta_archivo(p)
                )
                vistos_png = True
            continue
        items.append(etiqueta_archivo(p))
    return items


def _estado_validacion(
    errores: list[str] | None,
    avisos: list[str] | None,
) -> tuple[str, str]:
    """Devuelve (línea de estado, nivel: ok|aviso|error)."""
    errores = errores or []
    avisos = avisos or []
    if errores:
        n = len(errores)
        return (
            f"❌ Validación: {n} error{'es' if n != 1 else ''} "
            f"— conviene corregir antes de cotizar o fabricar",
            "error",
        )
    if avisos:
        n = len(avisos)
        return (
            f"⚠️ Validación: OK con {n} advertencia{'s' if n != 1 else ''} "
            f"(revisar detalle abajo)",
            "aviso",
        )
    return ("✅ Validación: sin observaciones", "ok")


def armar_mensaje_entrega(
    *,
    proyecto: dict | None,
    archivos: list[Path],
    link_visor_3d: str | None,
    errores: list[str] | None = None,
    avisos: list[str] | None = None,
    fallo_archivos: bool = False,
) -> list[str]:
    """Mensaje principal de cierre: resumen, validación, adjuntos y visor."""
    lineas: list[str] = ["🏗️ <b>Proyecto listo</b>", ""]

    tipo = _tipo_proyecto(proyecto)
    cliente = (proyecto or {}).get("cliente") if proyecto else None
    clave = (proyecto or {}).get("clave") if proyecto else None

    if tipo:
        lineas.append(f"<b>Tipo:</b> {_esc(tipo)}")
    if cliente:
        lineas.append(f"<b>Cliente:</b> {_esc(cliente)}")
    if clave:
        lineas.append(f"<b>Clave:</b> <code>{_esc(clave)}</code>")
    if tipo or cliente or clave:
        lineas.append("")

    estado, nivel = _estado_validacion(errores, avisos)
    lineas.append(estado)
    lineas.append("")

    entregables = _lista_entregables(archivos)
    if entregables:
        lineas.append("<b>📎 Se adjuntan:</b>")
        for item in entregables:
            lineas.append(f"• {_esc(item)}")
        lineas.append("")
    elif fallo_archivos:
        lineas.append(
            "⚠️ No pude generar planos/renders en el servidor. "
            "El diseño y la cotización en texto siguen siendo útiles."
        )
        lineas.append("")

    if link_visor_3d:
        lineas.append("🌐 <b>Visor 3D</b>")
        lineas.append(
            f'<a href="{html.escape(link_visor_3d, quote=True)}">'
            f"<b>Abrir modelo 3D interactivo</b></a>"
        )
        lineas.append("")

    if nivel == "error":
        lineas.append(
            "Corrige los datos del requerimiento (o indícame el ajuste) "
            "y vuelve a enviármelo para regenerar el proyecto."
        )
    elif nivel == "aviso":
        lineas.append(
            "Puedes usar los entregables; revisa las advertencias antes de cerrar con el cliente."
        )
    else:
        lineas.append("Revisa los archivos adjuntos y el visor. Si algo no cuadra, escríbeme la corrección.")

    return trocear("\n".join(lineas).strip(), _LIMITE)


def armar_detalle_validacion(
    errores: list[str] | None,
    avisos: list[str] | None,
) -> list[str]:
    """Detalle legible de validación (sin markdown ##). Vacío si no hay nada."""
    errores = [e for e in (errores or []) if e]
    avisos = [a for a in (avisos or []) if a]
    if not errores and not avisos:
        return []

    lineas: list[str] = ["📋 <b>Detalle de validación</b>", ""]
    if errores:
        lineas.append("<b>Errores a corregir:</b>")
        for e in errores:
            lineas.append(f"• {_esc(e)}")
        lineas.append("")
    if avisos:
        lineas.append("<b>Advertencias:</b>")
        for a in avisos:
            lineas.append(f"• {_esc(a)}")
    return trocear("\n".join(lineas).strip(), _LIMITE)


def ordenar_archivos_entrega(archivos: list[Path]) -> list[Path]:
    """Documentos primero (planos, cotización, despiece, 3D), renders al final."""

    def peso(p: Path) -> tuple[int, str]:
        low = p.name.lower()
        if low.startswith("planos_") and low.endswith(".pdf"):
            return (0, low)
        if low.startswith("cotizacion_") and low.endswith(".pdf"):
            return (1, low)
        if low.startswith("despiece_") and low.endswith(".xlsx"):
            return (2, low)
        if low.endswith((".glb", ".dae")):
            return (3, low)
        if low.endswith(".pdf"):
            return (4, low)
        if low.endswith(".xlsx"):
            return (5, low)
        if low.endswith(".png"):
            # perspectiva primero entre renders
            orden_png = {
                "render_perspectiva.png": 0,
                "render_planta.png": 1,
                "render_frontal.png": 2,
                "render_lateral.png": 3,
                "render_modulo_detalle.png": 4,
            }
            return (6, f"{orden_png.get(low, 9)}_{low}")
        return (7, low)

    return sorted(archivos, key=peso)
