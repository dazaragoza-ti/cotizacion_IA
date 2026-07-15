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
from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = letter

AZUL = HexColor("#1A3A8C")
GRIS_FILA = HexColor("#EFEFEF")
GRIS_TEXTO = HexColor("#404040")
VERDE = HexColor("#0F7B3F")

MARGEN = 40
COLS = [
    ("Código", MARGEN, 90),
    ("Descripción", MARGEN + 90, 220),
    ("Cant.", MARGEN + 310, 40),
    ("P. Unit.", MARGEN + 350, 90),
    ("Importe", MARGEN + 440, 92),
]
ALTURA_FILA = 16


def _items_cotizacion(datos: dict) -> list[dict]:
    items = datos.get("cotizacion") or []
    if items:
        return items
    return [
        {
            "codigo": m.get("codigo"),
            "descripcion": m.get("descripcion"),
            "cantidad": m.get("pzas"),
            "precio_unitario": m.get("precio"),
        }
        for m in datos.get("materiales", []) or []
        if m.get("precio") is not None
    ]


def _importe(it: dict) -> float:
    imp = it.get("importe")
    if imp is not None:
        return float(imp)
    try:
        return float(it.get("cantidad") or 0) * float(it.get("precio_unitario") or 0)
    except (TypeError, ValueError):
        return 0.0


def _dibujar_encabezado_pagina(c: canvas.Canvas, datos: dict) -> float:
    y = PAGE_H - 30
    c.setFillColor(AZUL)
    c.rect(0, y - 14, PAGE_W, 44, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(MARGEN, y + 6, f"COTIZACIÓN — {datos.get('proyecto', '') or datos.get('especificacion', '')}")
    c.setFont("Helvetica", 10)
    c.drawString(MARGEN, y - 8, f"{datos.get('clave', '')}  ·  {datos.get('cliente', '')}  ·  MXN sin IVA (mayoreo)")
    y -= 44

    c.setFillColor(GRIS_FILA)
    c.rect(MARGEN, y - ALTURA_FILA + 4, PAGE_W - 2 * MARGEN, ALTURA_FILA, fill=1, stroke=0)
    c.setFillColor(GRIS_TEXTO)
    c.setFont("Helvetica-Bold", 9)
    for titulo, x, ancho in COLS:
        alineacion_derecha = titulo in ("Cant.", "P. Unit.", "Importe")
        if alineacion_derecha:
            c.drawRightString(x + ancho - 4, y - ALTURA_FILA + 8, titulo)
        else:
            c.drawString(x + 4, y - ALTURA_FILA + 8, titulo)
    return y - ALTURA_FILA


def generar_cotizacion_pdf(datos: dict, salida: Path) -> Path | None:
    items = _items_cotizacion(datos)
    if not items:
        return None

    c = canvas.Canvas(str(salida), pagesize=letter)
    y = _dibujar_encabezado_pagina(c, datos)

    subtotal = 0.0
    c.setFont("Helvetica", 9)
    for i, it in enumerate(items):
        if y < 80:  # sin espacio para otra fila -- nueva pagina
            c.showPage()
            y = _dibujar_encabezado_pagina(c, datos)
            c.setFont("Helvetica", 9)

        imp = _importe(it)
        subtotal += imp
        c.setFillColor(GRIS_TEXTO)
        if i % 2 == 1:
            c.setFillColor(HexColor("#F8F8F8"))
            c.rect(MARGEN, y - ALTURA_FILA + 4, PAGE_W - 2 * MARGEN, ALTURA_FILA, fill=1, stroke=0)
        c.setFillColor(GRIS_TEXTO)
        c.drawString(COLS[0][1] + 4, y - ALTURA_FILA + 8, str(it.get("codigo") or ""))
        c.drawString(COLS[1][1] + 4, y - ALTURA_FILA + 8, str(it.get("descripcion") or "")[:55])
        c.drawRightString(COLS[2][1] + COLS[2][2] - 4, y - ALTURA_FILA + 8, str(it.get("cantidad") or ""))
        c.drawRightString(COLS[3][1] + COLS[3][2] - 4, y - ALTURA_FILA + 8, f"${float(it.get('precio_unitario') or 0):,.2f}")
        c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y - ALTURA_FILA + 8, f"${imp:,.2f}")
        y -= ALTURA_FILA

    y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(GRIS_TEXTO)
    c.drawRightString(COLS[3][1] + COLS[3][2] - 4, y, "Subtotal:")
    c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y, f"${subtotal:,.2f}")

    descuento_pct = float(datos.get("descuento_pct") or 0)
    total_final = subtotal
    if descuento_pct > 0:
        motivo = datos.get("motivo_descuento") or ""
        monto_descuento = subtotal * descuento_pct
        total_final = subtotal - monto_descuento
        y -= 16
        c.setFillColor(VERDE)
        c.drawRightString(COLS[3][1] + COLS[3][2] - 4, y, f"Descuento ({descuento_pct * 100:.0f}%):")
        c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y, f"-${monto_descuento:,.2f}")
        if motivo:
            c.setFont("Helvetica-Oblique", 8)
            c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y - 11, motivo[:70])
            y -= 11
            c.setFont("Helvetica-Bold", 10)
        y -= 16
        c.setFillColor(AZUL)
        c.drawRightString(COLS[3][1] + COLS[3][2] - 4, y, "TOTAL CON DESCUENTO:")
        c.drawRightString(COLS[4][1] + COLS[4][2] - 4, y, f"${total_final:,.2f}")

    y -= 24
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(GRIS_TEXTO)
    c.drawString(MARGEN, y, "IVA, flete e instalación se cotizan por separado.")

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
    print("PDF generado:" if resultado else "Sin items de cotizacion, no se genero PDF:", resultado or sys.argv[2])
