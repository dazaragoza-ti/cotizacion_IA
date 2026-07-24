"""
Genera el PDF de cotización -- reemplaza el XLSX de cotización que se
entregaba antes por Telegram. Si el proyecto trae "descuento_pct" (lo
calcula ventas_service.py, Cotizador IA), lo muestra junto con el motivo
y el total final ya descontado.

Uso:  python cotizacion_pdf.py datos.json salida.pdf
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = letter

AZUL = HexColor("#1A3A8C")
GRIS_FILA = HexColor("#EFEFEF")
GRIS_TEXTO = HexColor("#404040")
VERDE = HexColor("#0F7B3F")
ROJO_SUAVE = HexColor("#8B1A1A")

MARGEN = 40
COLS = [
    ("Código", MARGEN, 90),
    ("Descripción", MARGEN + 90, 220),
    ("Cant.", MARGEN + 310, 40),
    ("P. Unit.", MARGEN + 350, 90),
    ("Importe", MARGEN + 440, 92),
]
ALTURA_FILA = 16
# Espacio reservado al pie de totales (subtotal + descuento + total + nota)
ESPACIO_TOTALES = 110


def _fecha(datos: dict) -> str:
    return datos.get("fecha") or date.today().strftime("%d/%m/%Y")


def _items_cotizacion(datos: dict) -> list[dict]:
    """Items de cotización: lista explícita o materiales (con o sin precio)."""
    items = datos.get("cotizacion") or []
    if items:
        return items
    out = []
    for m in datos.get("materiales", []) or []:
        out.append({
            "codigo": m.get("codigo"),
            "descripcion": m.get("descripcion"),
            "cantidad": m.get("pzas"),
            "precio_unitario": m.get("precio"),
        })
    return out


def _importe(it: dict) -> float:
    imp = it.get("importe")
    if imp is not None:
        try:
            return float(imp)
        except (TypeError, ValueError):
            return 0.0
    try:
        pu = it.get("precio_unitario")
        if pu is None:
            return 0.0
        return float(it.get("cantidad") or 0) * float(pu)
    except (TypeError, ValueError):
        return 0.0


def _precio_unitario(it: dict) -> float | None:
    pu = it.get("precio_unitario")
    if pu is None:
        return None
    try:
        return float(pu)
    except (TypeError, ValueError):
        return None


def _dibujar_encabezado_pagina(c: canvas.Canvas, datos: dict, pagina: int,
                              total_paginas: int | None = None) -> float:
    y = PAGE_H - 28
    c.setFillColor(AZUL)
    c.rect(0, y - 18, PAGE_W, 50, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 15)
    titulo = datos.get("proyecto") or datos.get("especificacion") or "Cotización"
    c.drawString(MARGEN, y + 8, f"COTIZACIÓN — {str(titulo)[:55]}")
    c.setFont("Helvetica", 9)
    c.drawString(
        MARGEN, y - 8,
        f"Clave: {datos.get('clave') or '—'}   ·   "
        f"Cliente: {datos.get('cliente') or '—'}   ·   "
        f"Fecha: {_fecha(datos)}   ·   MXN sin IVA (mayoreo)",
    )
    if total_paginas:
        c.drawRightString(PAGE_W - MARGEN, y - 8, f"Pág. {pagina}/{total_paginas}")
    y -= 52

    # Fila de metadatos secundarios
    c.setFillColor(GRIS_TEXTO)
    c.setFont("Helvetica", 8)
    spec = datos.get("especificacion") or ""
    if spec:
        c.drawString(MARGEN, y, str(spec)[:90])
        y -= 12

    c.setFillColor(GRIS_FILA)
    c.rect(MARGEN, y - ALTURA_FILA + 4, PAGE_W - 2 * MARGEN, ALTURA_FILA, fill=1, stroke=0)
    c.setFillColor(GRIS_TEXTO)
    c.setFont("Helvetica-Bold", 9)
    for titulo_col, x, ancho in COLS:
        alineacion_derecha = titulo_col in ("Cant.", "P. Unit.", "Importe")
        if alineacion_derecha:
            c.drawRightString(x + ancho - 4, y - ALTURA_FILA + 8, titulo_col)
        else:
            c.drawString(x + 4, y - ALTURA_FILA + 8, titulo_col)
    return y - ALTURA_FILA


def _dibujar_totales(c: canvas.Canvas, y: float, subtotal: float,
                     datos: dict) -> float:
    """Bloque de totales; asume que hay espacio suficiente en la página."""
    descuento_pct = float(datos.get("descuento_pct") or 0)
    # Normalizar: a veces llega 10 (porcentaje) en vez de 0.10
    if descuento_pct > 1:
        descuento_pct = descuento_pct / 100.0

    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GRIS_TEXTO)
    c.drawRightString(COLS[3][1] + COLS[3][2] - 4, y, "Subtotal:")
    c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y, f"${subtotal:,.2f}")

    total_final = subtotal
    if descuento_pct > 0 and subtotal > 0:
        motivo = datos.get("motivo_descuento") or ""
        monto_descuento = subtotal * descuento_pct
        total_final = subtotal - monto_descuento
        y -= 16
        c.setFillColor(VERDE)
        c.drawRightString(
            COLS[3][1] + COLS[3][2] - 4, y,
            f"Descuento ({descuento_pct * 100:.1f}%):",
        )
        c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y, f"-${monto_descuento:,.2f}")
        if motivo:
            c.setFont("Helvetica-Oblique", 8)
            c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y - 11, str(motivo)[:70])
            y -= 11
            c.setFont("Helvetica-Bold", 10)

    y -= 18
    # Caja de total
    caja_y = y - 6
    c.setFillColor(AZUL)
    c.rect(COLS[3][1] - 20, caja_y - 4, COLS[4][1] + COLS[4][2] - COLS[3][1] + 24,
           22, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 11)
    etiqueta = "TOTAL CON DESCUENTO:" if descuento_pct > 0 else "TOTAL:"
    c.drawRightString(COLS[3][1] + COLS[3][2] - 4, caja_y + 2, etiqueta)
    c.drawRightString(COLS[4][1] + COLS[4][2] - 4, caja_y + 2, f"${total_final:,.2f}")

    y = caja_y - 18
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(GRIS_TEXTO)
    c.drawString(MARGEN, y, "IVA, flete e instalación se cotizan por separado.")
    c.drawString(MARGEN, y - 12, "Precios de mayoreo según catálogo PM (MXN).")
    return y - 12


def generar_cotizacion_pdf(datos: dict, salida: Path) -> Path | None:
    items = _items_cotizacion(datos)
    if not items:
        return None

    c = canvas.Canvas(str(salida), pagesize=letter)
    pagina = 1
    y = _dibujar_encabezado_pagina(c, datos, pagina)

    subtotal = 0.0
    sin_precio = 0
    c.setFont("Helvetica", 9)
    for i, it in enumerate(items):
        # Reservar espacio para el bloque de totales en la última página
        if y < ESPACIO_TOTALES + ALTURA_FILA:
            c.showPage()
            pagina += 1
            y = _dibujar_encabezado_pagina(c, datos, pagina)
            c.setFont("Helvetica", 9)

        imp = _importe(it)
        subtotal += imp
        pu = _precio_unitario(it)
        if pu is None:
            sin_precio += 1

        if i % 2 == 1:
            c.setFillColor(HexColor("#F8F8F8"))
            c.rect(MARGEN, y - ALTURA_FILA + 4, PAGE_W - 2 * MARGEN, ALTURA_FILA,
                   fill=1, stroke=0)
        c.setFillColor(GRIS_TEXTO)
        c.drawString(COLS[0][1] + 4, y - ALTURA_FILA + 8, str(it.get("codigo") or "")[:16])
        c.drawString(COLS[1][1] + 4, y - ALTURA_FILA + 8,
                     str(it.get("descripcion") or "")[:52])
        c.drawRightString(COLS[2][1] + COLS[2][2] - 4, y - ALTURA_FILA + 8,
                          str(it.get("cantidad") or ""))
        if pu is None:
            c.setFillColor(ROJO_SUAVE)
            c.drawRightString(COLS[3][1] + COLS[3][2] - 4, y - ALTURA_FILA + 8, "cotizar")
            c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y - ALTURA_FILA + 8, "—")
            c.setFillColor(GRIS_TEXTO)
        else:
            c.drawRightString(COLS[3][1] + COLS[3][2] - 4, y - ALTURA_FILA + 8,
                              f"${pu:,.2f}")
            c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y - ALTURA_FILA + 8,
                              f"${imp:,.2f}")
        y -= ALTURA_FILA

    if y < ESPACIO_TOTALES:
        c.showPage()
        pagina += 1
        y = _dibujar_encabezado_pagina(c, datos, pagina)
        # Evitar tabla vacía: solo totales en esta página
        y -= 8

    y -= 10
    _dibujar_totales(c, y, subtotal, datos)

    if sin_precio:
        c.setFont("Helvetica-Oblique", 8)
        c.setFillColor(ROJO_SUAVE)
        c.drawString(
            MARGEN, 36,
            f"Nota: {sin_precio} ítem(s) sin precio de catálogo — aparecen como «cotizar».",
        )

    c.save()
    return salida


def generar(datos: dict, out_dir) -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    salida = out_dir / f"Cotizacion_{datos.get('clave', 'PROYECTO')}.pdf"
    resultado = generar_cotizacion_pdf(datos, salida)
    return [resultado] if resultado else []


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python cotizacion_pdf.py datos.json salida.pdf")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        datos_proyecto = json.load(f)
    resultado = generar_cotizacion_pdf(datos_proyecto, Path(sys.argv[2]))
    print("PDF generado:" if resultado else "Sin items de cotizacion, no se genero PDF:",
          resultado or sys.argv[2])
