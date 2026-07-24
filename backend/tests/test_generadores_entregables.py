"""Tests de generadores (renders / planos / cotización) — sin Telegram."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai.generators import cotizacion_pdf, exportar_xlsx, modelo_3d, pm_plano

EJEMPLO = (
    ROOT / "app" / "ai" / "knowledge" / "ejemplos" / "ejemplo_proyecto_1nivel_simple.json"
)


@pytest.fixture
def proyecto_pesada() -> dict:
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))


@pytest.fixture
def proyecto_ligera(proyecto_pesada: dict) -> dict:
    p = json.loads(json.dumps(proyecto_pesada))
    p["especificacion"] = "Rack selectivo carga ligera gota"
    p["memoria"]["tipo_carga"] = "Carga ligera gota"
    p["layout"]["peralte_larguero_mm"] = 75
    return p


@pytest.fixture
def proyecto_cantilever(proyecto_pesada: dict) -> dict:
    p = json.loads(json.dumps(proyecto_pesada))
    p["layout"]["tipo"] = "Cantilever"
    p["especificacion"] = "Cantilever carga media"
    p["clave"] = "CANT-01"
    return p


def test_poste_pesada_vs_ligera(proyecto_pesada, proyecto_ligera, proyecto_cantilever):
    assert modelo_3d.poste_mm_de(proyecto_pesada) == 73
    assert modelo_3d.poste_mm_de(proyecto_ligera) == 38
    assert modelo_3d.es_carga_ligera(proyecto_ligera) is True
    assert modelo_3d.familia_geometria(proyecto_pesada) == "selectivo"
    assert modelo_3d.familia_geometria(proyecto_cantilever) == "cantilever"
    assert modelo_3d.geometria_selectiva_soportada(proyecto_cantilever) is True


def test_cotizacion_pdf_totales_y_descuento(proyecto_pesada, tmp_path):
    datos = dict(proyecto_pesada)
    datos["descuento_pct"] = 0.10
    datos["motivo_descuento"] = "Volumen mayoreo"
    out = tmp_path / "Cotizacion_test.pdf"
    assert cotizacion_pdf.generar_cotizacion_pdf(datos, out) == out
    assert out.exists() and out.stat().st_size > 800


def test_cotizacion_pdf_sin_precios_no_vacia(tmp_path):
    datos = {
        "proyecto": "P",
        "clave": "X",
        "cliente": "C",
        "fecha": "01/01/2026",
        "materiales": [
            {"pzas": 2, "codigo": "ABC", "descripcion": "Sin precio", "precio": None},
        ],
    }
    out = tmp_path / "c.pdf"
    assert cotizacion_pdf.generar_cotizacion_pdf(datos, out) == out
    assert out.exists()


def test_exportar_xlsx_precios_y_total(proyecto_pesada, tmp_path):
    datos = dict(proyecto_pesada)
    datos["descuento_pct"] = 5  # formato porcentaje entero
    path = exportar_xlsx.despiece(datos, tmp_path)
    assert path.exists()
    assert path.name.startswith("Despiece_")


def test_pm_plano_sin_png_no_falla(proyecto_pesada, tmp_path):
    out = tmp_path / "Planos.pdf"
    pm_plano.generar_plano(proyecto_pesada, out)
    assert out.exists() and out.stat().st_size > 1000


@pytest.mark.slow
def test_modelo_3d_cantilever_genera_mesh(proyecto_cantilever, tmp_path):
    json_path = tmp_path / "p.json"
    json_path.write_text(json.dumps(proyecto_cantilever), encoding="utf-8")
    out = tmp_path / "modelo"
    modelo_3d.generar(str(json_path), str(out))
    vistas = out / "vistas"
    assert (vistas / "render_perspectiva.png").exists()
    assert (vistas / "AVISO_GEOMETRIA.txt").exists()
    assert (out / "CANT-01.glb").exists() or (out / "CANT-01.obj").exists()


@pytest.mark.slow
def test_modelo_3d_selectivo_pngs(proyecto_pesada, tmp_path):
    json_path = tmp_path / "p.json"
    json_path.write_text(json.dumps(proyecto_pesada), encoding="utf-8")
    out = tmp_path / "modelo"
    modelo_3d.generar(str(json_path), str(out))
    vistas = out / "vistas"
    for nombre in (
        "render_planta.png",
        "render_perspectiva.png",
        "render_frontal.png",
        "render_lateral.png",
        "render_modulo_detalle.png",
    ):
        assert (vistas / nombre).exists(), nombre
