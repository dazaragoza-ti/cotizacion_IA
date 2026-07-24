"""
Smoke E2E offline del pipeline mínimo de cotización.

Flujo: cuestionario → contrato → validador (sin Anthropic de pago).
Si un test necesitara LLM, marcar @pytest.mark.slow y skip sin API key.
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

from app.ai.pipelines import cuestionario as c
from app.ai.schemas.proyecto_pm import errores_contrato_proyecto
from app.engineering import validator_engine
from app.services.catalogo_pm_service import _aplanar_catalogo_anidado


def _catalogo_local() -> list[dict]:
    raw = json.loads(
        (Path(_BACKEND) / "app" / "ai" / "knowledge" / "catalogo_pm.json").read_text(
            encoding="utf-8"
        )
    )
    return _aplanar_catalogo_anidado(raw)


def _proyecto_fixture_selectivo() -> dict:
    path = (
        Path(_BACKEND)
        / "app"
        / "ai"
        / "knowledge"
        / "ejemplos"
        / "ejemplo_proyecto_1nivel_simple.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_e2e_smoke_cuestionario_a_validador_offline():
    """Simula cotización mínima: cuestionario completo → JSON dorado → contrato+validador."""
    uid = 9001
    c.limpiar(uid)
    pasos = [
        "Necesito un rack selectivo para refacciones",
        "10 m de frente, 8 m de fondo, 6 m de altura libre",
        "Solo tarima",
        "Tarima 1.2 x 1.0 m, 800 kg, 2 por nivel",
        "4 niveles con nivel a piso",
        "Carga pesada",
        "Montacargas contrabalanceado, pasillo 3 m",
    ]
    last = None
    for msg in pasos:
        last = c.procesar(uid, msg)
    assert last is not None
    assert last.accion == "generar"
    assert last.texto_completo.strip()

    # En producción Claude emitiría JSON; aquí usamos dorado de disco (sin LLM).
    proyecto = _proyecto_fixture_selectivo()
    assert errores_contrato_proyecto(proyecto) == []
    r = validator_engine.validar(proyecto, catalogo=_catalogo_local())
    assert not r.errores, r.errores


def test_e2e_regenerar_salta_cuestionario():
    uid = 9002
    c.limpiar(uid)
    assert c.es_comando_regenerar("regenerar")
    assert c.es_comando_regenerar("regenera el 3D")
    assert not c.es_comando_regenerar("necesito un rack selectivo")
    texto = c.texto_regeneracion("regenerar")
    assert "REGENERAR" in texto
    d = c.procesar(uid, texto, hay_proyecto_anterior=True)
    assert d.accion == "generar"


@pytest.mark.slow
def test_e2e_con_llm_marcado_slow_skip_sin_key():
    """Placeholder: requiere ANTHROPIC_API_KEY. No corre en CI sin key."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY ausente — smoke LLM omitido")
    # Con key: aquí se podría llamar claude_client; se deja como guarda.
    assert True
