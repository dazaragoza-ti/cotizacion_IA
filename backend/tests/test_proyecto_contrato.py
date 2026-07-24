"""
Tests del contrato tipado del proyectista y del bloque de reglas en context builder.

Corre con: `python backend/tests/test_proyecto_contrato.py`
"""
from __future__ import annotations

import os
import sys

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from app.ai.schemas.proyecto_pm import errores_contrato_proyecto


def _proyecto_ok() -> dict:
    return {
        "proyecto": "Demo",
        "clave": "X001",
        "cliente": "Acme",
        "especificacion": "Rack selectivo carga pesada gota",
        "layout": {
            "tipo": "Selectivo",
            "modulos_x": 4,
            "modulos_y": 2,
            "frente_mm": 2504,
            "fondo_mm": 917,
            "pasillo_mm": 3000,
            "niveles": [0, 1800, 3600],
            "altura_total_mm": 4000,
            "peralte_larguero_mm": 150,
        },
        "materiales": [
            {"pzas": 10, "codigo": "CRG-1", "descripcion": "Cabecera", "precio": 100},
        ],
        "memoria": {"carga_modulo_kg": 2000},
        "observaciones": ["ok"],
    }


def test_contrato_valido_sin_errores():
    assert errores_contrato_proyecto(_proyecto_ok()) == []


def test_contrato_sin_layout():
    data = _proyecto_ok()
    del data["layout"]
    errs = errores_contrato_proyecto(data)
    assert errs and any("layout" in e for e in errs)


def test_contrato_niveles_sin_cero():
    data = _proyecto_ok()
    data["layout"]["niveles"] = [1800, 3600]
    errs = errores_contrato_proyecto(data)
    assert errs and any("niveles" in e for e in errs)


def test_contrato_none_vacio():
    assert errores_contrato_proyecto(None) == []


def test_inferir_tipo_rack_y_bloque_reglas_sin_supabase():
    """Sin deps de runtime: stubea clientes externos y valida el formateo."""
    import sys
    import types

    class _FakeQuery:
        def select(self, *a, **k):
            return self

        def eq(self, *a, **k):
            return self

        def in_(self, *a, **k):
            return self

        def order(self, *a, **k):
            return self

        def limit(self, *a, **k):
            return self

        def upsert(self, *a, **k):
            return self

        def insert(self, *a, **k):
            return self

        def delete(self, *a, **k):
            return self

        def execute(self):
            return types.SimpleNamespace(data=[])

    class _FakeClient:
        def table(self, *a, **k):
            return _FakeQuery()

        def rpc(self, *a, **k):
            return _FakeQuery()

    def _ensure_stub(mod_name: str, **attrs):
        if mod_name in sys.modules:
            return
        m = types.ModuleType(mod_name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[mod_name] = m

    _ensure_stub("supabase", create_client=lambda *a, **k: _FakeClient(), Client=_FakeClient)
    _ensure_stub("groq", Groq=lambda *a, **k: object())
    _ensure_stub("anthropic", Anthropic=lambda *a, **k: object(), AsyncAnthropic=lambda *a, **k: object())

    from app.ai import context_builder as cb

    assert cb._inferir_tipo_rack("quiero cantilever", None) == "cantilever"
    assert cb._inferir_tipo_rack("carga ligera gota", None) == "ligera"
    assert cb._inferir_tipo_rack(
        "ajuste",
        {"especificacion": "Rack selectivo carga pesada gota"},
    ) == "Rack selectivo carga pesada gota"

    original = cb.consultar_reglas_armado
    try:
        cb.consultar_reglas_armado = lambda tipo="todos": [  # type: ignore[assignment]
            {
                "condicion": "reemplaza_por:codigo=A->to=B",
                "descripcion": "A se reemplaza por B",
                "accion": "usar B",
                "activa": True,
            }
        ]
        bloque = cb._bloque_reglas_armado("todos")
        assert "reglas_armado" in bloque
        assert "usar B" in bloque

        texto = cb.construir_descripcion_extendida(
            descripcion="necesito un rack",
            proyecto_anterior=None,
            correcciones_similares=None,
        )
        assert "reglas_armado" in texto
        assert "Mensaje del cliente:" in texto
    finally:
        cb.consultar_reglas_armado = original  # type: ignore[assignment]


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
            except Exception as e:
                fallos += 1
                print(f"ERROR {nombre}: {e}")
    raise SystemExit(fallos)
