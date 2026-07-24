"""Orquesta los generadores deterministas sobre el JSON de proyecto.

Encadena:
  1. generators/modelo_3d.py     → modelo 3D (OBJ/DAE/GLB) + renders PNG
  2. generators/render_html.py   → render 3D interactivo HTML (desde el GLB)
  3. generators/pm_plano.py      → PDF de planos (4 hojas), incrustando los PNG
  4. generators/exportar_xlsx.py → XLSX de despiece
  5. generators/cotizacion_pdf.py → PDF de cotización (con descuento si aplica)

Devuelve la lista de archivos generados, listos para enviar por Telegram.
Es tolerante a fallos: si un generador falla, sigue con lo que se pueda.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger("pipeline")

# app/ai/pipelines/pipeline.py -> app/ai/generators/ (carpeta hermana, no hija)
GEN_DIR = Path(__file__).parent.parent / "generators"
MODELO_3D = GEN_DIR / "modelo_3d.py"
PM_PLANO = GEN_DIR / "pm_plano.py"
EXPORTAR_XLSX = GEN_DIR / "exportar_xlsx.py"
COTIZACION_PDF = GEN_DIR / "cotizacion_pdf.py"
RENDER_HTML = GEN_DIR / "render_html.py"

# PNG que produce modelo_3d.py (en <out>/vistas/) → clave de render que lee pm_plano.py
RENDER_KEYS = {
    "render_path": "render_perspectiva.png",
    "render_frontal_path": "render_frontal.png",
    "render_lateral_path": "render_lateral.png",
    "render_detalle_path": "render_modulo_detalle.png",
}
PNGS_A_ENVIAR = [
    "render_perspectiva.png",
    "render_planta.png",
    "render_frontal.png",
    "render_lateral.png",
    "render_modulo_detalle.png",
]


def _run(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=600,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-2000:] or "error desconocido")
    return proc.stdout


def correr_pipeline(
    proyecto: dict, work_dir: Path,
    descuento_pct: float = 0.0, motivo_descuento: str = "",
) -> list[Path]:
    """Ejecuta los generadores. `work_dir` debe ser un directorio temporal.

    `descuento_pct`/`motivo_descuento` vienen del Cotizador IA
    (ventas_service.calcular_descuento, ver proyecto_pm_service.py) -- se
    inyectan en el JSON para que cotizacion_pdf.py los muestre, sin que
    ningun otro generador (planos, 3D, despiece) sepa nada de descuentos.
    """
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    clave = proyecto.get("clave", "PROYECTO")

    proyecto_con_descuento = dict(proyecto)
    if descuento_pct > 0:
        proyecto_con_descuento["descuento_pct"] = descuento_pct
        proyecto_con_descuento["motivo_descuento"] = motivo_descuento

    json_path = work_dir / "proyecto.json"
    json_path.write_text(
        json.dumps(proyecto_con_descuento, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    salidas: list[Path] = []
    out3d = work_dir / "modelo"
    vistas = out3d / "vistas"

    # 1) Modelo 3D + renders PNG
    try:
        _run([str(MODELO_3D), str(json_path), str(out3d)], cwd=work_dir)
    except Exception as e:
        log.warning("modelo_3d falló: %s", e)

    for png in PNGS_A_ENVIAR:
        p = vistas / png
        if p.exists():
            salidas.append(p)
    # Archivos 3D útiles (DAE importable en SketchUp, GLB para visores)
    glb_path = None
    for ext in (".dae", ".glb"):
        p = out3d / f"{clave}{ext}"
        if p.exists():
            salidas.append(p)
            if ext == ".glb":
                glb_path = p

    # 1.5) Render 3D interactivo HTML — determinista, desde el GLB real
    if glb_path:
        html_path = work_dir / f"render_3d_{clave}.html"
        try:
            _run([str(RENDER_HTML), str(json_path), str(glb_path), str(html_path)],
                 cwd=work_dir)
            if html_path.exists():
                salidas.append(html_path)
                log.info("Render HTML determinista generado: %s (%d KB)",
                         html_path.name, html_path.stat().st_size // 1024)
        except Exception as e:
            log.warning("render_html falló: %s", e)

    # 2) PDF de planos — inyecta los PNG generados para que los incruste
    proyecto_pdf = dict(proyecto)
    faltan_png = []
    for clave_render, nombre_png in RENDER_KEYS.items():
        p = vistas / nombre_png
        if p.exists():
            proyecto_pdf[clave_render] = str(p)
        else:
            faltan_png.append(nombre_png)
    if faltan_png:
        log.warning(
            "PNG faltantes para planos (%s): se usarán esquemas/placeholders",
            ", ".join(faltan_png),
        )

    json_pdf = work_dir / "proyecto_pdf.json"
    json_pdf.write_text(
        json.dumps(proyecto_pdf, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    pdf_path = work_dir / f"Planos_{clave}.pdf"
    try:
        _run([str(PM_PLANO), str(json_pdf), str(pdf_path)], cwd=work_dir)
        if pdf_path.exists():
            salidas.append(pdf_path)
    except Exception as e:
        log.warning("pm_plano falló: %s", e)

    # 3) XLSX de despiece (desde el JSON original)
    try:
        _run([str(EXPORTAR_XLSX), str(json_path), str(work_dir)], cwd=work_dir)
    except Exception as e:
        log.warning("exportar_xlsx falló: %s", e)
    despiece_path = work_dir / f"Despiece_{clave}.xlsx"
    if despiece_path.exists():
        salidas.append(despiece_path)

    # 4) PDF de cotización (desde el JSON con descuento inyectado, si aplica)
    cotizacion_path = work_dir / f"Cotizacion_{clave}.pdf"
    try:
        _run([str(COTIZACION_PDF), str(json_path), str(cotizacion_path)], cwd=work_dir)
        if cotizacion_path.exists():
            salidas.append(cotizacion_path)
    except Exception as e:
        log.warning("cotizacion_pdf falló: %s", e)

    return salidas
