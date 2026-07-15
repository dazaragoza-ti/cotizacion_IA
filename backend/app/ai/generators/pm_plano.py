"""
Generador de planos PM La Piedad — formato FO-DD-8.10.

Toma un diccionario con los datos del proyecto y produce un PDF de 4 hojas:
  1) Vista en planta / layout
  2) Alzado frontal y lateral acotado
  3) Despiece y lista de materiales + memoria de cálculo
  4) Notas generales y render (placeholder si no hay imagen)

Uso:
    from pm_plano import generar_plano
    generar_plano(datos_proyecto, "salida.pdf")
"""

from datetime import date
from pathlib import Path

from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


PAGE_W, PAGE_H = landscape(letter)  # 792 x 612 pts — carta apaisada

PM_AZUL = HexColor("#00B5E2")
PM_GRIS = HexColor("#404040")
COTA = HexColor("#B00020")


def _draw_cajetin(c, hoja, total, datos, vista_titulo, escala):
    """Dibuja el cajetín PM La Piedad (esquina inferior derecha)."""
    x0 = PAGE_W - 340
    y0 = 8
    w = 332
    h = 130

    c.setLineWidth(0.6)
    c.setStrokeColor(black)
    c.rect(x0, y0, w, h, stroke=1, fill=0)

    # Banda superior: logo + cliente + área
    banda_h = 28
    c.line(x0, y0 + h - banda_h, x0 + w, y0 + h - banda_h)

    logo = Path(__file__).parent / "logo_pm.png"
    if logo.exists():
        c.drawImage(str(logo), x0 + 5, y0 + h - banda_h + 4, width=75, height=20,
                    mask='auto', preserveAspectRatio=True)

    c.setFont("Helvetica-Bold", 7)
    c.drawString(x0 + 88, y0 + h - 13, datos.get("cliente", "CLIENTE"))
    c.setFont("Helvetica-Oblique", 6)
    c.setFillColor(PM_GRIS)
    c.drawString(x0 + 88, y0 + h - 22, "Ingenieria - Diseno de Racks")
    c.setFillColor(black)

    # Bloque de revisiones (columna izquierda)
    rev_w = 84
    rev_top = y0 + h - banda_h
    rev_h = h - banda_h
    c.line(x0 + rev_w, rev_top, x0 + rev_w, y0)
    c.setFont("Helvetica-Bold", 5.5)
    c.drawString(x0 + 2, rev_top - 7, "Rev.")
    c.drawString(x0 + 22, rev_top - 7, "Elaboro")
    c.drawString(x0 + 52, rev_top - 7, "Fecha")
    c.line(x0, rev_top - 9, x0 + rev_w, rev_top - 9)
    c.setFont("Helvetica", 5)
    for i in range(3):
        yline = rev_top - 9 - (i + 1) * 8
        if i < 2:
            c.line(x0, yline, x0 + rev_w, yline)
        c.drawString(x0 + 3, yline + 2, f"R{i}")

    # Bloque principal a la derecha
    bx = x0 + rev_w
    by = y0
    bw = w - rev_w
    bh = h - banda_h

    rows = [
        ("Codigo/Descripcion", datos.get("proyecto", ""), 2),
        ("Linea o proyecto", datos.get("clave", ""), 1),
        ("Material", str(datos.get("material", "Acero rolado"))[:24], 1),
        ("Especificacion", str(datos.get("especificacion", ""))[:32], 2),
        ("Calibre/Espesor", datos.get("calibre", ""), 1),
        ("Dim. de corte", datos.get("dim_corte", "-"), 1),
        ("Elaboro", datos.get("elaboro", ""), 1),
        ("Reviso", datos.get("reviso", ""), 1),
        ("Aprobo", datos.get("aprobo", ""), 1),
        ("Acotacion", "mm", 1),
        ("Escala", escala, 1),
        ("Fecha", datos.get("fecha", date.today().strftime("%d/%m/%Y")), 1),
        ("Hoja", f"{hoja} / {total}", 1),
        ("Revision", datos.get("revision", "R0"), 1),
    ]

    cell_w = bw / 2
    cell_h = 10
    cur_x = bx
    cur_y = by + bh - cell_h
    col = 0
    for label, value, span in rows:
        if span == 2:
            if col == 1:
                cur_x = bx
                cur_y -= cell_h
                col = 0
            c.setStrokeColor(HexColor("#BBBBBB"))
            c.rect(cur_x, cur_y, bw, cell_h, stroke=1, fill=0)
            c.setFont("Helvetica", 5.5)
            c.setFillColor(PM_GRIS)
            c.drawString(cur_x + 2, cur_y + cell_h - 4, label + ":")
            c.setFillColor(black)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(cur_x + 72, cur_y + 2, str(value)[:55])
            cur_y -= cell_h
            cur_x = bx
            col = 0
        else:
            c.setStrokeColor(HexColor("#BBBBBB"))
            c.rect(cur_x, cur_y, cell_w, cell_h, stroke=1, fill=0)
            c.setFont("Helvetica", 5.5)
            c.setFillColor(PM_GRIS)
            c.drawString(cur_x + 2, cur_y + cell_h - 4, label + ":")
            c.setFillColor(black)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(cur_x + 58, cur_y + 2, str(value)[:20])
            if col == 0:
                cur_x = bx + cell_w
                col = 1
            else:
                cur_x = bx
                col = 0
                cur_y -= cell_h

    c.setStrokeColor(black)

    # Tolerancias + sello
    c.setFont("Helvetica-Oblique", 5.5)
    c.setFillColor(PM_GRIS)
    c.drawString(x0 + 2, y0 + 4, "Tol. gral. salvo indicadas: Lineal +/-0.5 mm")
    c.drawRightString(x0 + w - 2, y0 + 4, "FO-DD-8.10")
    c.setFillColor(black)

    # Texto de propiedad intelectual (arriba de todo)
    c.setFont("Helvetica-Oblique", 5)
    c.setFillColor(PM_GRIS)
    c.drawCentredString(
        PAGE_W / 2, PAGE_H - 8,
        "La información contenida en este documento es propiedad intelectual de "
        "GRUPO PM LA PIEDAD. Se prohíbe su uso para cualquier fin sin previa autorización."
    )
    c.setFillColor(black)

    # Título de la vista (a la izquierda del cajetín)
    if vista_titulo:
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(220, 90, vista_titulo)
        c.setFont("Helvetica-Oblique", 7)
        c.drawCentredString(220, 76, "Tolerancia: +/-2.00 cm")


def _cota(c, x1, y1, x2, y2, texto, offset=10, vertical=False):
    """Dibuja una línea de cota simple con texto."""
    c.setStrokeColor(COTA)
    c.setLineWidth(0.4)
    if vertical:
        xt = x1 + offset
        c.line(x1, y1, xt + 4, y1)
        c.line(x2, y2, xt + 4, y2)
        c.line(xt, y1, xt, y2)
        # flechitas
        c.line(xt, y1, xt - 2, y1 + 3)
        c.line(xt, y1, xt + 2, y1 + 3)
        c.line(xt, y2, xt - 2, y2 - 3)
        c.line(xt, y2, xt + 2, y2 - 3)
        c.setFillColor(COTA)
        c.setFont("Helvetica", 6)
        c.saveState()
        c.translate(xt - 2, (y1 + y2) / 2)
        c.rotate(90)
        c.drawCentredString(0, 2, texto)
        c.restoreState()
    else:
        yt = y1 + offset
        c.line(x1, y1, x1, yt + 4)
        c.line(x2, y2, x2, yt + 4)
        c.line(x1, yt, x2, yt)
        c.line(x1, yt, x1 + 3, yt - 2)
        c.line(x1, yt, x1 + 3, yt + 2)
        c.line(x2, yt, x2 - 3, yt - 2)
        c.line(x2, yt, x2 - 3, yt + 2)
        c.setFillColor(COTA)
        c.setFont("Helvetica", 6)
        c.drawCentredString((x1 + x2) / 2, yt + 2, texto)
    c.setStrokeColor(black)
    c.setFillColor(black)


def _hoja_planta_con_fondo(c, datos):
    """Hoja 1 alternativa: Vista en planta usando layout del almacén como fondo,
    con zonas de rack superpuestas."""
    layout = datos["layout"]
    bg = layout.get("background_image")
    zones = layout.get("zones", [])

    # Área de dibujo (deja espacio para cajetín)
    ox, oy = 20, 160
    aw, ah = PAGE_W - 360, PAGE_H - 200

    bg_path = Path(__file__).parent / bg
    if bg_path.exists():
        c.drawImage(str(bg_path), ox, oy, width=aw, height=ah,
                    preserveAspectRatio=True, mask='auto')

    # Overlay de cada zona naranja con los racks
    naranja = HexColor("#FF7A00")
    naranja_rel = HexColor("#FFC080")
    total_modulos = 0
    for idx, z in enumerate(zones, 1):
        x = ox + z["x_pct"] * aw
        y = oy + (1 - z["y_pct"] - z["h_pct"]) * ah
        w = z["w_pct"] * aw
        h = z["h_pct"] * ah
        # Bloque general de la zona
        c.setStrokeColor(naranja)
        c.setFillColor(naranja_rel)
        c.setLineWidth(1.2)
        c.rect(x, y, w, h, stroke=1, fill=1)
        # Subdivisión por módulos (si orientación es horizontal divide en w)
        n = z.get("modulos", 1)
        orient = z.get("orientacion", "horizontal")
        c.setStrokeColor(black)
        c.setLineWidth(0.4)
        if orient == "horizontal":
            for i in range(1, n):
                xx = x + (w / n) * i
                c.line(xx, y, xx, y + h)
        else:
            for i in range(1, n):
                yy = y + (h / n) * i
                c.line(x, yy, x + w, yy)
        # Etiqueta con número y nombre
        c.setFillColor(black)
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 2, y + h + 2, f"Z{idx}: {z['nombre']} ({n} mod)")
        total_modulos += n

    # Leyenda
    c.setFont("Helvetica-Bold", 9)
    c.drawString(ox, oy - 14,
                 f"PLANTA CALLE 11 — Racks en zonas naranjas  ·  "
                 f"Total: {total_modulos} módulos de {layout['frente_mm']/1000:.2f} x "
                 f"{layout['fondo_mm']/1000:.2f} m, altura {layout['altura_total_mm']/1000:.1f} m")
    c.setFont("Helvetica", 7)
    c.setFillColor(PM_GRIS)
    c.drawString(ox, oy - 26,
                 "Cada bloque naranja = zona de instalación. Las líneas internas "
                 "indican los módulos individuales del rack.")
    c.setFillColor(black)

    _draw_cajetin(c, 1, 4, datos, "VISTA EN PLANTA", layout.get("escala", "S/E"))
    c.showPage()


def _hoja_planta(c, datos):
    """Hoja 1: Vista en planta del rack en el almacén."""
    layout = datos["layout"]
    if layout.get("background_image"):
        return _hoja_planta_con_fondo(c, datos)
    modulos_x = layout["modulos_x"]      # número de módulos a lo largo
    modulos_y = layout["modulos_y"]      # filas de racks
    frente = layout["frente_mm"]         # frente del módulo (mm)
    fondo = layout["fondo_mm"]           # fondo de la cabecera (mm)
    pasillo = layout["pasillo_mm"]       # ancho de pasillo (mm)

    # Área de dibujo
    ox, oy = 60, 220
    aw, ah = 600, 280

    # Calcular escala automática
    total_x = modulos_x * frente + (modulos_x - 1) * 50
    total_y = modulos_y * fondo + (modulos_y - 1) * pasillo
    sx = aw / total_x
    sy = ah / total_y
    s = min(sx, sy) * 0.85
    escala_real = int(1 / s)

    # Centrar
    draw_w = total_x * s
    draw_h = total_y * s
    cx = ox + (aw - draw_w) / 2
    cy = oy + (ah - draw_h) / 2

    # Dibujar cada módulo de rack
    c.setStrokeColor(PM_AZUL)
    c.setFillColor(HexColor("#E6F7FC"))
    c.setLineWidth(0.7)
    for j in range(modulos_y):
        for i in range(modulos_x):
            mx = cx + i * (frente + 50) * s
            my = cy + j * (fondo + pasillo) * s
            c.rect(mx, my, frente * s, fondo * s, stroke=1, fill=1)
            # Marcar postes en esquinas
            c.setFillColor(black)
            poste = 2
            for px, py in [(mx, my), (mx + frente * s - poste, my),
                           (mx, my + fondo * s - poste),
                           (mx + frente * s - poste, my + fondo * s - poste)]:
                c.rect(px, py, poste, poste, stroke=0, fill=1)
            c.setFillColor(HexColor("#E6F7FC"))

    # Pasillos: flecha de circulación
    c.setStrokeColor(PM_GRIS)
    c.setLineWidth(0.3)
    for j in range(modulos_y - 1):
        py = cy + j * (fondo + pasillo) * s + fondo * s + pasillo * s / 2
        c.setDash(2, 2)
        c.line(cx, py, cx + draw_w, py)
        c.setDash()
        c.setFont("Helvetica-Oblique", 6)
        c.setFillColor(PM_GRIS)
        c.drawString(cx + 2, py - 7, f"Pasillo {pasillo} mm")

    c.setFillColor(black)
    c.setStrokeColor(black)

    # Cotas globales
    _cota(c, cx, cy + draw_h, cx + draw_w, cy + draw_h, f"{total_x} mm", offset=15)
    _cota(c, cx, cy, cx, cy + draw_h, f"{total_y} mm", offset=-25, vertical=True)

    # Norte
    c.setFont("Helvetica-Bold", 8)
    c.drawString(ox + aw - 30, oy + ah - 10, "N ↑")

    # Leyenda
    c.setFont("Helvetica", 7)
    c.drawString(60, oy - 12, f"Módulos: {modulos_x} × {modulos_y}    "
                              f"Frente: {frente} mm    Fondo: {fondo} mm    "
                              f"Pasillo: {pasillo} mm")

    _draw_cajetin(c, 1, 4, datos, "VISTA EN PLANTA", f"1:{escala_real}")
    c.showPage()


def _alzado_render_o_esquema(c, datos, vista, render_key, x, y, w, h, titulo):
    """Dibuja un alzado usando el render 3D si existe, o esquema si no.

    Devuelve (cy_image, ch_image): coordenadas y altura efectiva del bloque
    visual para alinear cotas al lado.
    """
    layout = datos["layout"]
    niveles = layout["niveles"]
    altura_total = layout["altura_total_mm"]
    frente = layout["frente_mm"]
    fondo = layout["fondo_mm"]

    render_path = _resolve_path(datos.get(render_key))

    # Marco del recuadro
    c.setStrokeColor(HexColor("#DDDDDD"))
    c.setLineWidth(0.3)
    c.rect(x, y, w, h, stroke=1, fill=0)

    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y + h + 8, titulo)

    if render_path:
        # Usar render 3D centrado dentro del recuadro
        c.drawImage(str(render_path), x + 5, y + 5, width=w - 10, height=h - 10,
                    preserveAspectRatio=True, mask='auto')
        return x, y, w, h

    # ----- Fallback esquemático mejorado -----
    if vista == "frontal":
        dim_x = frente
    else:
        dim_x = fondo
    dim_y = altura_total
    pad = 30
    sx = (w - 2 * pad) / dim_x
    sy = (h - 2 * pad) / dim_y
    s = min(sx, sy)
    dw = dim_x * s
    dh = dim_y * s
    cx = x + (w - dw) / 2
    cy = y + (h - dh) / 2

    poste_w = 5
    # Postes
    c.setFillColor(PM_AZUL)
    c.rect(cx, cy, poste_w, dh, stroke=0, fill=1)
    c.rect(cx + dw - poste_w, cy, poste_w, dh, stroke=0, fill=1)
    # Placa base
    c.setFillColor(HexColor("#333333"))
    c.rect(cx - 3, cy - 4, poste_w + 6, 4, stroke=0, fill=1)
    c.rect(cx + dw - poste_w - 3, cy - 4, poste_w + 6, 4, stroke=0, fill=1)

    if vista == "frontal":
        # Largueros + entrepaños por nivel
        for h_nivel in niveles[1:]:
            yn = cy + h_nivel * s
            c.setFillColor(PM_AZUL)
            c.rect(cx + poste_w, yn, dw - 2 * poste_w, 2.5, stroke=0, fill=1)
            # Entrepaño (banda naranja delgada)
            c.setFillColor(HexColor("#E07020"))
            c.rect(cx + poste_w, yn + 2.5, dw - 2 * poste_w, 2.5, stroke=0, fill=1)
    else:
        # Lateral: X-bracing en zigzag entre postes
        c.setStrokeColor(PM_AZUL)
        c.setLineWidth(0.6)
        n_paneles = max(3, len(niveles))
        paso = dh / n_paneles
        x1 = cx + poste_w / 2
        x2 = cx + dw - poste_w / 2
        for i in range(n_paneles):
            z_bot = cy + i * paso
            z_top = cy + (i + 1) * paso
            # Horizontal en cada nivel del panel
            c.line(x1, z_top, x2, z_top)
            if i % 2 == 0:
                c.line(x1, z_bot, x2, z_top)
            else:
                c.line(x2, z_bot, x1, z_top)
        # Largueros vistos de canto (puntos naranja)
        for h_nivel in niveles[1:]:
            yn = cy + h_nivel * s
            c.setFillColor(HexColor("#E07020"))
            c.rect(cx + poste_w + 2, yn, dw - 2 * poste_w - 4, 3, stroke=0, fill=1)

    c.setFillColor(black)
    c.setStrokeColor(black)
    return cx, cy, dw, dh


def _hoja_alzado(c, datos):
    """Hoja 2: Alzado frontal y lateral usando renders 3D + cotas."""
    layout = datos["layout"]
    niveles = layout["niveles"]
    altura_total = layout["altura_total_mm"]
    frente = layout["frente_mm"]
    fondo = layout["fondo_mm"]
    peralte = layout.get("peralte_larguero_mm", 150)

    # ===== ALZADO FRONTAL (izquierda) =====
    fx, fy, fw, fh = 80, 200, 320, 310
    bx, by, bw, bh = _alzado_render_o_esquema(c, datos, "frontal",
                                                "render_frontal_path",
                                                fx, fy, fw, fh,
                                                "ALZADO FRONTAL")

    # Cotas verticales a la IZQUIERDA del recuadro (niveles)
    cota_x = fx - 10
    # Mapeo de mm a coordenadas del recuadro
    z_map = lambda mm: fy + 10 + (fh - 20) * mm / altura_total
    prev = 0
    for h_nivel in niveles[1:]:
        delta = h_nivel - prev
        _cota(c, cota_x, z_map(prev), cota_x, z_map(h_nivel),
              f"{delta}", offset=-12, vertical=True)
        prev = h_nivel
    if altura_total > prev:
        _cota(c, cota_x, z_map(prev), cota_x, z_map(altura_total),
              f"{altura_total - prev}", offset=-12, vertical=True)
    # Cota total (más a la izquierda)
    _cota(c, cota_x - 30, z_map(0), cota_x - 30, z_map(altura_total),
          f"{altura_total} mm", offset=-12, vertical=True)
    # Cota frente abajo
    _cota(c, fx + 10, fy - 8, fx + fw - 10, fy - 8, f"{frente} mm", offset=-12)
    # Etiqueta peralte
    c.setFont("Helvetica", 6.5)
    c.setFillColor(PM_GRIS)
    c.drawString(fx + fw + 4, fy + fh - 20,
                 f"Peralte larguero: {peralte} mm")
    c.drawString(fx + fw + 4, fy + fh - 30,
                 f"Niveles: {len(niveles) - 1}  (sin contar piso)")
    c.setFillColor(black)

    # ===== ALZADO LATERAL (derecha) =====
    lx, ly, lwd, lhd = 460, 200, 250, 310
    _alzado_render_o_esquema(c, datos, "lateral",
                              "render_lateral_path",
                              lx, ly, lwd, lhd,
                              "ALZADO LATERAL")
    # Cota fondo abajo
    _cota(c, lx + 10, ly - 8, lx + lwd - 10, ly - 8, f"{fondo} mm", offset=-12)
    # Cota altura izquierda
    z_map_l = lambda mm: ly + 10 + (lhd - 20) * mm / altura_total
    _cota(c, lx - 10, z_map_l(0), lx - 10, z_map_l(altura_total),
          f"{altura_total} mm", offset=-12, vertical=True)

    _draw_cajetin(c, 2, 4, datos, "ALZADO FRONTAL Y LATERAL", "S/E")
    c.showPage()


def _hoja_despiece(c, datos):
    """Hoja 3: Despiece, lista de materiales con precios y memoria de cálculo."""
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, PAGE_H - 40, "DESPIECE, LISTA DE MATERIALES Y COTIZACION")
    c.setFont("Helvetica-Oblique", 7)
    c.drawString(50, PAGE_H - 52, "Tolerancia: ±2.00 cm    Acotación: mm    Precios MAYOREO sin IVA (MXN)")

    materiales = datos.get("materiales", [])
    headers = ["PZAS", "CODIGO", "DESCRIPCION", "COLOR", "P. UNIT.", "IMPORTE"]
    col_x = [50, 95, 180, 470, 555, 625]
    col_w = [45, 85, 290, 85, 70, 110]

    y = PAGE_H - 80
    c.setFillColor(PM_AZUL)
    c.rect(50, y - 2, sum(col_w), 14, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8)
    for i, h in enumerate(headers):
        if i >= 4:
            c.drawRightString(col_x[i] + col_w[i] - 4, y + 3, h)
        else:
            c.drawString(col_x[i] + 3, y + 3, h)
    c.setFillColor(black)
    y -= 14

    # El subtotal se calcula SIEMPRE sobre TODOS los materiales, sin importar
    # cuantas filas quepan visualmente en la hoja -- antes se acumulaba
    # dentro del mismo for que corta (break) al llenarse la pagina, asi que
    # un despiece con mas materiales de los que caben en la hoja dejaba el
    # TOTAL mostrado abajo silenciosamente por debajo del real.
    subtotal = sum(
        (fila.get("pzas", 0) or 0) * (fila.get("precio", 0) or 0)
        for fila in materiales
    )

    c.setFont("Helvetica", 7)
    n_mostrados = 0
    for fila in materiales:
        if y < 240:
            break
        c.setStrokeColor(HexColor("#CCCCCC"))
        c.line(50, y, 50 + sum(col_w), y)
        pzas = fila.get("pzas", 0)
        precio = fila.get("precio", 0) or 0
        importe = pzas * precio
        c.drawRightString(col_x[0] + col_w[0] - 4, y + 3, str(pzas))
        c.drawString(col_x[1] + 3, y + 3, str(fila.get("codigo", ""))[:14])
        c.drawString(col_x[2] + 3, y + 3, str(fila.get("descripcion", ""))[:62])
        c.drawString(col_x[3] + 3, y + 3, str(fila.get("color", ""))[:14])
        if precio:
            c.drawRightString(col_x[4] + col_w[4] - 4, y + 3, f"${precio:,.2f}")
            c.drawRightString(col_x[5] + col_w[5] - 4, y + 3, f"${importe:,.2f}")
        else:
            c.drawRightString(col_x[4] + col_w[4] - 4, y + 3, "cotizar")
            c.drawRightString(col_x[5] + col_w[5] - 4, y + 3, "—")
        y -= 11
        n_mostrados += 1
    if n_mostrados < len(materiales):
        c.setFont("Helvetica-Oblique", 6.5)
        c.setFillColor(COTA)
        c.drawString(50, y - 2, f"+ {len(materiales) - n_mostrados} material(es) adicional(es) -- ver despiece completo en Excel/PDF de cotizacion.")
        c.setFillColor(black)
    c.setStrokeColor(black)

    # Totales (esquina derecha, sobre cajetín)
    ttop = 215
    iva = subtotal * 0.16
    instalacion = datos.get("memoria", {}).get("instalacion_mxn", 0)
    neto = subtotal + instalacion
    total = neto + iva
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(PM_AZUL)
    c.rect(540, ttop - 60, 195, 70, stroke=0, fill=1)
    c.setFillColor(white)
    c.drawString(545, ttop - 8, "RESUMEN COTIZACION (MXN)")
    c.setFont("Helvetica", 8)
    c.drawString(545, ttop - 20, "Sub-total materiales:")
    c.drawRightString(730, ttop - 20, f"${subtotal:,.2f}")
    c.drawString(545, ttop - 30, "Instalación:")
    c.drawRightString(730, ttop - 30, f"${instalacion:,.2f}")
    c.drawString(545, ttop - 40, "Neto:")
    c.drawRightString(730, ttop - 40, f"${neto:,.2f}")
    c.drawString(545, ttop - 50, "IVA 16%:")
    c.drawRightString(730, ttop - 50, f"${iva:,.2f}")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(545, ttop - 60 + 3, "TOTAL:")
    c.drawRightString(730, ttop - 60 + 3, f"${total:,.2f}")
    c.setFillColor(black)

    # Memoria de cálculo (bloque inferior IZQUIERDO solamente, no choca con totales/cajetín)
    my0 = 160
    c.setFont("Helvetica-Bold", 9)
    c.drawString(50, my0 + 65, "MEMORIA DE CALCULO Y CAPACIDADES")
    c.setFont("Helvetica", 8)
    memoria = datos.get("memoria", {})
    tipo_sistema = datos['layout'].get('tipo', 'Selectivo')
    tipo_carga = memoria.get('tipo_carga', 'Carga pesada gota')
    tarima = memoria.get('tarima_lxa', 'N/A')
    peso_t = memoria.get('peso_tarima_kg', '—')
    t_nivel = memoria.get('tarimas_nivel', '—')
    n_niv = len(datos['layout']['niveles'])
    c_niv = memoria.get('carga_nivel_kg', '—')
    c_mod = memoria.get('carga_modulo_kg', '—')
    c_marco = memoria.get('cap_marco_kg', '4500')
    f_seg = memoria.get('factor_seguridad', '1.5')
    anclaje_default = 'Taquete arpón 1/2" x 4½ (TEM-0019)'
    anclaje = memoria.get('anclaje', anclaje_default)
    mont = memoria.get('montacargas', '—')
    pas = datos['layout'].get('pasillo_mm', '—')
    lineas = [
        f"Tipo de sistema: {tipo_sistema}  |  Tipo de carga: {tipo_carga}",
        f"Tarima de diseño: {tarima} mm  |  Peso por tarima: {peso_t} kg",
        f"Tarimas por nivel: {t_nivel}  |  Niveles: {n_niv}  |  Carga por nivel: {c_niv} kg",
        f"Carga total por módulo: {c_mod} kg  |  Capacidad nominal del marco: {c_marco} kg/sección",
        f"Factor de seguridad: {f_seg}  |  Anclaje: {anclaje}",
        f"Montacargas previsto: {mont}  |  Ancho de pasillo: {pas} mm",
    ]
    y = my0 + 50
    for ln in lineas:
        c.drawString(50, y, ln)
        y -= 11

    # Notas (limitadas al ancho izquierdo para no chocar con cajetín)
    from reportlab.lib.utils import simpleSplit
    c.setFont("Helvetica-Bold", 8)
    c.drawString(50, y - 4, "Observaciones:")
    c.setFont("Helvetica", 6.5)
    max_width = 690  # ocupar todo el ancho hasta el cajetín tope (cajetín está abajo)
    obs_y_min = 145  # detener antes de tocar el cajetín
    for obs in datos.get("observaciones", []):
        if y < obs_y_min:
            break
        wrapped = simpleSplit(f"- {obs}", "Helvetica", 6.5, max_width)
        for ln in wrapped:
            y -= 8
            if y < obs_y_min:
                break
            c.drawString(58, y - 4, ln)

    _draw_cajetin(c, 3, 4, datos, "", "S/E")
    c.showPage()


def _resolve_path(p):
    """Resuelve un path: absoluto > CWD > junto al script."""
    if not p:
        return None
    for cand in [Path(p), Path.cwd() / p, Path(__file__).parent / p]:
        if cand.exists():
            return cand
    return None


def _hoja_notas_render(c, datos):
    """Hoja 4: Render principal del modelo 3D + detalle + notas generales."""
    render = datos.get("render_path")
    render_detalle = datos.get("render_detalle_path")
    render_path = _resolve_path(render)
    detalle_path = _resolve_path(render_detalle)

    # Render principal (grande, izquierda-arriba)
    if render_path:
        c.drawImage(str(render_path), 30, 270, width=440, height=230,
                    preserveAspectRatio=True, mask='auto')
    else:
        c.setFillColor(HexColor("#F5F5F5"))
        c.rect(30, 270, 440, 230, stroke=1, fill=1)
        c.setFillColor(PM_GRIS)
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(250, 385, "[ Render del proyecto ]")
        c.setFillColor(black)

    # Render detalle (mediano, izquierda-abajo)
    if detalle_path:
        c.drawImage(str(detalle_path), 30, 50, width=260, height=210,
                    preserveAspectRatio=True, mask='auto')
    else:
        c.setFillColor(HexColor("#F5F5F5"))
        c.rect(50, 200, 400, 300, stroke=1, fill=1)
        c.setFillColor(PM_GRIS)
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(250, 350,
                            "[ Espacio para render del proyecto ]")
        c.setFillColor(black)

    c.setFont("Helvetica-Oblique", 6)
    c.drawCentredString(250, 190,
                        "Las imágenes mostradas son solo una representación "
                        "y en ningún momento representan al mueble final.")

    # Notas generales
    nx, ny = 470, 500
    c.setFont("Helvetica-Bold", 10)
    c.drawString(nx, ny, "NOTAS GENERALES")
    c.setFont("Helvetica-Bold", 8)
    c.drawString(nx, ny - 14, "CONDICIONES DE SEGURIDAD:")
    c.setFont("Helvetica", 7)
    notas = [
        "• La instalación del producto requiere estar sobre una superficie sólida y nivelada,",
        "  adecuada para la colocación de postería y correcto funcionamiento.",
        "• No ejercer cargas verticales en los pasamanos.",
        "• El no cumplir con las condiciones de seguridad y uso del producto puede dañar al",
        "  mismo o a la persona.",
        "• NO APLICAN REQUISITOS LEGALES Y REGLAMENTARIOS.",
        "• NORMA ASTM e ISO.",
        "",
        "NOTA IMPORTANTE: EN CASO DE QUE SE AUTORICE EL PROYECTO, VISITAR EL SITIO",
        "PARA INSPECCIONAR MEDIDAS Y LUGAR.",
    ]
    y = ny - 28
    for ln in notas:
        c.drawString(nx, y, ln)
        y -= 10

    _draw_cajetin(c, 4, 4, datos, "RENDER Y NOTAS GENERALES", "S/E")
    c.showPage()


def generar_plano(datos, salida):
    """Genera el PDF completo del proyecto.

    Estructura esperada de `datos`:
    {
      "proyecto": "PROYECTO X853-C",
      "clave": "X853-C",
      "cliente": "GOBIERNO DE MICHOACAN",
      "elaboro": "Xocotzin", "reviso": "...", "aprobo": "...",
      "fecha": "22/05/2026", "revision": "R0",
      "material": "Acero rolado en frío",
      "especificacion": "Rack selectivo carga pesada gota",
      "calibre": "Cal 14",
      "dim_corte": "—",
      "layout": {
         "tipo": "Selectivo",
         "modulos_x": 8, "modulos_y": 3,
         "frente_mm": 2724, "fondo_mm": 1100, "pasillo_mm": 3000,
         "niveles": [0, 1800, 3600],  # alturas desde piso
         "altura_total_mm": 7000,
         "peralte_larguero_mm": 150
      },
      "materiales": [
         {"pzas": 33, "codigo": "TEM-0365-AZ",
          "descripcion": "POSTE GOTA 670 DOBLE CARGA PESADA",
          "color": "AZUL", "obs": ""},
         ...
      ],
      "memoria": {
         "tipo_carga": "Carga pesada gota",
         "tarima_lxa": "1200 x 1000", "peso_tarima_kg": 1000,
         "tarimas_nivel": 3, "carga_nivel_kg": 3000,
         "carga_modulo_kg": 9000, "cap_marco_kg": 4500,
         "factor_seguridad": 1.5,
         "anclaje": "Taquete arpón 1/2\" x 4½ TEM-0019",
         "montacargas": "Contrabalanceado, pasillo 3.0 m"
      },
      "observaciones": ["..."],
      "render_path": null
    }
    """
    c = canvas.Canvas(str(salida), pagesize=(PAGE_W, PAGE_H))
    c.setTitle(datos.get("proyecto", "Proyecto PM La Piedad"))
    c.setAuthor("GRUPO PM LA PIEDAD")
    _hoja_planta(c, datos)
    _hoja_alzado(c, datos)
    _hoja_despiece(c, datos)
    _hoja_notas_render(c, datos)
    c.save()
    return salida


if __name__ == "__main__":
    import json, sys
    if len(sys.argv) < 3:
        print("Uso: python pm_plano.py datos.json salida.pdf")
        sys.exit(1)
    with open(sys.argv[1]) as f:
        datos = json.load(f)
    generar_plano(datos, sys.argv[2])
    print(f"PDF generado: {sys.argv[2]}")
