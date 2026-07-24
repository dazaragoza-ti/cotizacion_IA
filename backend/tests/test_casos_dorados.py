"""
Casos dorados por tipo de rack — viven en knowledge/ejemplos/ (disco/git).
NO se suben a Supabase. Validan contrato + validator_engine (+ evaluación).

Corre: pytest tests/test_casos_dorados.py -q
O:     python -m app.engineering.evaluacion
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

EJEMPLOS = Path(_BACKEND) / "app" / "ai" / "knowledge" / "ejemplos"

from app.ai.schemas.proyecto_pm import errores_contrato_proyecto
from app.engineering import validator_engine
from app.engineering.tipo_rack import tipo_rack_de_proyecto
from app.services.catalogo_pm_service import _aplanar_catalogo_anidado


def _catalogo_local() -> list[dict]:
    raw = json.loads(
        (Path(_BACKEND) / "app" / "ai" / "knowledge" / "catalogo_pm.json").read_text(
            encoding="utf-8"
        )
    )
    return _aplanar_catalogo_anidado(raw)


def _jsons() -> list[Path]:
    if not EJEMPLOS.is_dir():
        return []
    return sorted(EJEMPLOS.glob("*.json"))


@pytest.mark.parametrize("path", _jsons(), ids=lambda p: p.name)
def test_contrato_dorado(path: Path):
    proyecto = json.loads(path.read_text(encoding="utf-8"))
    errs = errores_contrato_proyecto(proyecto)
    assert errs == [], f"{path.name}: {errs}"


@pytest.mark.parametrize("path", _jsons(), ids=lambda p: p.name)
def test_validador_dorado_sin_errores(path: Path):
    """Errores bloqueantes = 0. Advertencias se toleran en dorados históricos."""
    proyecto = json.loads(path.read_text(encoding="utf-8"))
    # Quitar meta-clave de documentación
    proyecto = {k: v for k, v in proyecto.items() if not k.startswith("_")}
    cat = _catalogo_local()
    r = validator_engine.validar(proyecto, catalogo=cat)
    assert not r.errores, f"{path.name}: {r.errores}"


def test_cobertura_tipos_rack_dorados():
    """Debe haber al menos un dorado selectivo, cantilever y entrepiso."""
    tipos = set()
    for path in _jsons():
        proyecto = json.loads(path.read_text(encoding="utf-8"))
        proyecto = {k: v for k, v in proyecto.items() if not k.startswith("_")}
        tipos.add(tipo_rack_de_proyecto(proyecto))
        # Naming convention
        name = path.name.lower()
        if "cantilever" in name:
            assert tipo_rack_de_proyecto(proyecto) == "cantilever"
        if "entrepiso" in name:
            assert tipo_rack_de_proyecto(proyecto) == "entrepiso"
    assert "pesada" in tipos or "ligera" in tipos, f"faltan selectivos: {tipos}"
    assert "cantilever" in tipos, f"falta cantilever: {tipos}"
    assert "entrepiso" in tipos, f"falta entrepiso: {tipos}"


def test_evaluacion_modulo_medible():
    """evaluacion.evaluar_ejemplos reporta métrica validos/total."""
    from app.engineering.evaluacion import evaluar_ejemplos

    # Stub supabase vía catálogo local: monkeypatch consultar_catalogo_pm
    import app.engineering.evaluacion as ev
    import app.services.catalogo_pm_service as cat_svc

    original = cat_svc.consultar_catalogo_pm
    cat_svc.consultar_catalogo_pm = _catalogo_local
    try:
        res = ev.evaluar_ejemplos()
    finally:
        cat_svc.consultar_catalogo_pm = original

    assert res.total >= 3
    # Al menos cantilever + entrepiso + un selectivo deben existir
    nombres = {r.archivo for r in res.resultados}
    assert any("cantilever" in n for n in nombres)
    assert any("entrepiso" in n for n in nombres)
    # Métrica imprimible
    assert "/" in res.resumen()
    fallidos = [r for r in res.resultados if not r.valido]
    assert not fallidos, f"dorados inválidos: {[(r.archivo, r.errores_validador) for r in fallidos]}"
