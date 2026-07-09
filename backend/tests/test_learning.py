"""
Tests del planificador de aprendizaje (Sprint 2, Fase 1/3) — lógica pura, sin BD.

Corre con: `python backend/tests/test_learning.py`
"""
import os
import sys

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.engineering.learning import (
    metricas_de_uso,
    planificar_aprendizaje,
    RELACION_REEMPLAZO,
    RELACION_COMPATIBLE,
    RELACION_EVITAR,
)
from app.engineering.sku_diff import diff_skus


def _P(mats):
    return {"materiales": [{"codigo": c, "pzas": n} for c, n in mats]}


def test_reemplazo_genera_metricas_y_relacion():
    diff = diff_skus(_P([("LRS7355", 8)]), _P([("LRS7410", 8)]))
    plan = planificar_aprendizaje(diff)
    assert ("LRS7355", "veces_reemplazado") in plan.metricas
    assert ("LRS7410", "veces_recomendado") in plan.metricas
    assert plan.relaciones == [("LRS7355", RELACION_REEMPLAZO, "LRS7410")]


def test_eliminado_genera_rechazo():
    diff = diff_skus(_P([("TEN-1", 4), ("CA-9", 2)]), _P([("CA-9", 2)]))
    plan = planificar_aprendizaje(diff)
    assert ("TEN-1", "veces_rechazado") in plan.metricas
    # CA-9 (otra familia) siguió presente cuando se quitó TEN-1 → evitar_con.
    assert plan.relaciones == [("TEN-1", RELACION_EVITAR, "CA-9")]


def test_reemplazo_genera_compatible_con_resto_del_proyecto():
    diff = diff_skus(
        _P([("LRS7355", 8), ("CA-9", 2)]),
        _P([("LRS7410", 8), ("CA-9", 2)]),
    )
    plan = planificar_aprendizaje(diff)
    assert ("LRS7410", RELACION_COMPATIBLE, "CA-9") in plan.relaciones


def test_evitar_con_no_empareja_misma_familia():
    # CA-1 y CA-9 son de la misma familia ("CA") — no deben generar evitar_con
    # entre sí (son alternativas, no un combo real).
    diff = diff_skus(_P([("CA-1", 1), ("CA-9", 2)]), _P([("CA-9", 2)]))
    plan = planificar_aprendizaje(diff)
    assert plan.relaciones == []


def test_sin_cambios_plan_vacio():
    diff = diff_skus(_P([("A1", 1)]), _P([("A1", 1)]))
    assert planificar_aprendizaje(diff).vacio


def test_metricas_de_uso():
    pares = metricas_de_uso(_P([("A1", 2), ("B2", 5)]))
    assert set(pares) == {("A1", "veces_usado"), ("B2", "veces_usado")}
    assert metricas_de_uso(None) == []


if __name__ == "__main__":
    fallos = 0
    for nombre, fn in sorted(globals().items()):
        if nombre.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"OK   {nombre}")
            except AssertionError as e:
                fallos += 1
                print(f"FAIL {nombre}: {e}")
    print("\n" + ("TODOS LOS TESTS PASARON" if not fallos else f"{fallos} fallaron"))
    sys.exit(1 if fallos else 0)
