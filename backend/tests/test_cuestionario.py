"""
Tests del cuestionario por tipo de rack (Telegram).

Corre con: `python backend/tests/test_cuestionario.py`
"""
from __future__ import annotations

import os
import sys

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.ai.pipelines import cuestionario as c


def _reset(uid: int = 1) -> None:
    c.limpiar(uid)


def test_detecta_tipo():
    assert c.detectar_tipo_rack("rack selectivo carga pesada") == "selectivo"
    assert c.detectar_tipo_rack("necesito cantiléver para tubos") == "cantilever"
    assert c.detectar_tipo_rack("entrepiso mezzanine 12x8") == "entrepiso"
    assert c.detectar_tipo_rack("hola quiero cotizar") is None


def test_pregunta_tipo_primero():
    _reset(7)
    d = c.procesar(7, "Quiero cotizar un almacén")
    assert d.accion == "preguntar"
    assert "Tipo de sistema" in d.mensaje or "selectivo" in d.mensaje.lower()
    assert c.estado_de(7).tipo_rack is None


def test_flujo_selectivo_completo():
    _reset(8)
    pasos = [
        "Necesito un rack selectivo para harina",
        "10 m de frente, 8 m de fondo, 6 m de altura libre",
        "Solo tarima",
        "Tarima 1.2 x 1.0 m, 800 kg, 2 por nivel",
        "4 niveles con nivel a piso",
        "Carga pesada",
        "Montacargas contrabalanceado, pasillo 3 m",
    ]
    last = None
    for msg in pasos:
        last = c.procesar(8, msg)
    assert last is not None
    assert last.accion == "generar"
    assert "selectivo" in last.texto_completo.lower() or "[Tipo de rack: selectivo]" in last.texto_completo


def test_montacargas_manual_sin_pasillo_numerico():
    _reset(9)
    c.procesar(9, "selectivo para cajas de refacciones")
    c.procesar(9, "12 m frente, 10 m fondo, 5 m altura")
    c.procesar(9, "solo tarima")
    c.procesar(9, "tarima 1.0 x 1.2 m, 500 kg, 2 por nivel")
    c.procesar(9, "3 niveles")
    c.procesar(9, "carga ligera")
    d = c.procesar(9, "acceso manual con patín, sin montacargas")
    assert d.accion == "generar"


def test_dims_sin_numeros_no_cuentan():
    presentes = c.detectar_campos_presentes(
        "selectivo bodega grande con buen frente y fondo",
        tipo="selectivo",
    )
    assert "dimensiones_espacio" not in presentes


def test_correccion_salta_cuestionario():
    _reset(10)
    d = c.procesar(10, "está mal el diseño del 3D", hay_proyecto_anterior=True)
    assert d.accion == "generar"
    assert d.texto_completo == "está mal el diseño del 3D"


def test_cancelar():
    assert c.es_comando_cancelar("/cancelar")
    assert c.es_comando_cancelar("/reset")
    assert not c.es_comando_cancelar("cancelar por favor")


def test_cantilever_pide_carga_y_estructura():
    _reset(11)
    d = c.procesar(11, "cantilever para tubos de acero")
    assert d.accion == "preguntar"
    est = c.estado_de(11)
    assert est.tipo_rack == "cantilever"
    keys = {f.key for f in est.faltantes}
    assert "carga_cantilever" in keys
    assert "estructura_cantilever" in keys


def test_entrepiso_campos():
    _reset(12)
    d = c.procesar(12, "necesito un entrepiso")
    assert c.estado_de(12).tipo_rack == "entrepiso"
    keys = {f.key for f in c.estado_de(12).faltantes}
    assert "geometria_entrepiso" in keys
    assert "carga_entrepiso" in keys
    assert d.accion == "preguntar"


if __name__ == "__main__":
    tests = [
        test_detecta_tipo,
        test_pregunta_tipo_primero,
        test_flujo_selectivo_completo,
        test_montacargas_manual_sin_pasillo_numerico,
        test_dims_sin_numeros_no_cuentan,
        test_correccion_salta_cuestionario,
        test_cancelar,
        test_cantilever_pide_carga_y_estructura,
        test_entrepiso_campos,
    ]
    failed = 0
    for fn in tests:
        try:
            fn()
            print(f"OK  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERR  {fn.__name__}: {e}")
    if failed:
        print(f"\n{failed} test(s) fallaron")
        sys.exit(1)
    print(f"\n{len(tests)} tests OK")
