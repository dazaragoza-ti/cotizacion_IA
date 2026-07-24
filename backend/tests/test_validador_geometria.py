"""Tests del validador geométrico (selectivo)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.ai.generators import validador_geometria as vg
from app.ai.generators import modelo_3d as m3d

EJEMPLO = (
    ROOT / "app" / "ai" / "knowledge" / "ejemplos" / "ejemplo_proyecto_1nivel_simple.json"
)


def _proyecto() -> dict:
    return json.loads(EJEMPLO.read_text(encoding="utf-8"))


def test_validar_modulo_selectivo_ok():
    reporte = vg.validar_modulo(_proyecto())
    assert "ok" in reporte and "defectos" in reporte
    assert isinstance(reporte["defectos"], list)
    # El ejemplo de 1 nivel simple debe pasar las reglas (o al menos no crashear).
    # Si hay defectos, deben tener shape canónico.
    for d in reporte["defectos"]:
        assert "regla" in d and "descripcion" in d and "severidad" in d


def test_validar_corrida_shape():
    reporte = vg.validar_corrida(_proyecto(), n_modulos=2)
    assert reporte["ok"] in (True, False)
    assert isinstance(reporte["defectos"], list)


def test_overlap_1d():
    assert vg._overlap_1d(0, 10, 5, 15) == 5
    assert vg._overlap_1d(0, 5, 10, 15) == -5


def test_familia_cantilever_y_entrepiso_construyen_mesh():
    base = _proyecto()
    cant = json.loads(json.dumps(base))
    cant["layout"]["tipo"] = "Cantilever"
    cant["clave"] = "CANT-T"
    assert m3d.familia_geometria(cant) == "cantilever"
    meshes = m3d.construir_modulo(0, 0, cant)
    assert len(meshes) >= 4

    ent = json.loads(json.dumps(base))
    ent["layout"]["tipo"] = "Entrepiso"
    ent["clave"] = "ENT-T"
    assert m3d.familia_geometria(ent) == "entrepiso"
    meshes_e = m3d.construir_modulo(0, 0, ent)
    assert len(meshes_e) >= 4


def test_normalizar_tipo_rack():
    from app.engineering.tipo_rack import normalizar_tipo_rack, tipo_rack_de_proyecto
    assert normalizar_tipo_rack("Rack selectivo carga pesada gota") == "pesada"
    assert normalizar_tipo_rack("carga ligera") == "ligera"
    assert normalizar_tipo_rack("cantiléver doble") == "cantilever"
    assert normalizar_tipo_rack("mezzanine") == "entrepiso"
    assert tipo_rack_de_proyecto({"especificacion": "Selectivo carga ligera"}) == "ligera"
