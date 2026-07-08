"""
Tests del SkuDiffExtractor (Sprint 2, Fase 0c).

Corre sin dependencias: `python backend/tests/test_sku_diff.py`
(o bajo pytest si está instalado: `pytest backend/tests/test_sku_diff.py`).
"""
import os
import sys

# Permite ejecutar el archivo directamente desde cualquier cwd.
_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.engineering.sku_diff import diff_skus, extraer_piezas, normalizar_sku


def _P(mats):
    """Construye un proyecto mínimo con la lista de (codigo, pzas)."""
    return {"materiales": [{"codigo": c, "pzas": n} for c, n in mats]}


def test_reemplazo_simple():
    d = diff_skus(_P([("LRS7355", 8), ("CRG7138", 4)]),
                  _P([("LRS7410", 8), ("CRG7138", 4)]))
    assert d.reemplazos == [("LRS7355", "LRS7410")]
    assert not d.agregados and not d.eliminados


def test_normaliza_sufijo_de_color():
    assert normalizar_sku("LRS7355-AZ") == "LRS7355"
    d = diff_skus(_P([("LRS7355-AZ", 8)]), _P([("LRS7410-NA", 8)]))
    assert d.reemplazos == [("LRS7355", "LRS7410")]


def test_cambio_de_cantidad_no_es_reemplazo():
    d = diff_skus(_P([("CA-500", 10)]), _P([("CA-500", 14)]))
    assert d.reemplazos == []
    assert d.cambios_cantidad == [("CA-500", 10, 14)]


def test_familias_distintas_no_emparejan():
    d = diff_skus(_P([("TEN-1", 4)]), _P([("CA-9", 4)]))
    assert d.reemplazos == []
    assert d.eliminados == ["TEN-1"] and d.agregados == ["CA-9"]


def test_suma_duplicados_en_despiece():
    assert extraer_piezas(_P([("X1", 2), ("X1", 3)])) == {"X1": 5}


def test_none_safety():
    assert diff_skus(None, _P([("A1", 1)])).agregados == ["A1"]
    assert not diff_skus(None, None).hubo_cambio_de_piezas


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
    print("\n" + ("TODOS LOS TESTS PASARON" if not fallos else f"{fallos} test(s) fallaron"))
    sys.exit(1 if fallos else 0)
