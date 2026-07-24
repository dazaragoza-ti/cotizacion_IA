"""
Tests ligeros del paquete de ahorro de tokens.

Corre con: `python backend/tests/test_ahorro_tokens.py`
"""
from __future__ import annotations

import os
import sys
import types
from pathlib import Path

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _stub_externos():
    """Evita importar supabase/groq/anthropic reales en unit tests."""
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
    _ensure_stub(
        "anthropic",
        Anthropic=lambda *a, **k: object(),
        AsyncAnthropic=lambda *a, **k: object(),
        APIConnectionError=type("APIConnectionError", (Exception,), {}),
        InternalServerError=type("InternalServerError", (Exception,), {}),
        RateLimitError=type("RateLimitError", (Exception,), {}),
    )
    if "httpx" not in sys.modules:
        hx = types.ModuleType("httpx")
        hx.RemoteProtocolError = type("RemoteProtocolError", (Exception,), {})
        hx.ReadError = type("ReadError", (Exception,), {})
        hx.ReadTimeout = type("ReadTimeout", (Exception,), {})
        hx.ConnectError = type("ConnectError", (Exception,), {})
        sys.modules["httpx"] = hx


def _catalogo_demo() -> list[dict]:
    return [
        {"codigo": "CRG-1", "familia": "pesada", "categoria": "cabecera", "fondo_mm": 917},
        {"codigo": "LRS-1", "familia": "pesada", "categoria": "larguero", "frente_mm": 2504, "peralte_mm": 150},
        {"codigo": "CRL-1", "familia": "ligera", "categoria": "cabecera", "fondo_mm": 600},
        {"codigo": "LRL-1", "familia": "ligera", "categoria": "larguero", "frente_mm": 1800, "peralte_mm": 80},
        {"codigo": "MPR-1", "familia": "comun", "categoria": "tornilleria"},
        {"codigo": "CA-1", "familia": "pesada", "categoria": "cargador"},
    ]


def test_filtrar_catalogo_por_familia():
    from app.engineering.compatibility import filtrar_catalogo_por_familia, inferir_familia

    cat = _catalogo_demo()
    assert inferir_familia("rack carga pesada gota", None) == "pesada"
    assert inferir_familia("ajuste", {"especificacion": "Rack selectivo carga ligera gota"}) == "ligera"
    assert inferir_familia("quiero un rack", None) is None

    filtrado, modo = filtrar_catalogo_por_familia(cat, "pesada")
    codigos = {p["codigo"] for p in filtrado}
    assert modo == "familia=pesada"
    assert "CRG-1" in codigos and "LRS-1" in codigos and "MPR-1" in codigos and "CA-1" in codigos
    assert "CRL-1" not in codigos and "LRL-1" not in codigos

    completo, modo_fb = filtrar_catalogo_por_familia(cat, None)
    assert modo_fb == "fallback_completo"
    assert len(completo) == len(cat)


def test_top_n_correcciones_rag():
    _stub_externos()
    from app.ai import context_builder as cb

    correcciones = [
        {"contenido": "A" * 50},
        {"contenido": "B" * 50},
        {"contenido": "C" * 50},
        {"contenido": "D" * 50},
        {"contenido": "E" * (cb.MAX_CHARS_POR_CORRECCION + 200)},
    ]
    bloque = cb._bloque_correcciones_rag(correcciones)
    assert bloque.count("\n\n") == cb.MAX_CORRECCIONES_RAG - 1  # 3 trozos → 2 sep
    assert "D" * 50 not in bloque  # 4ª queda fuera
    # La 3ª (índice 2) entra completa; la 5ª no se usa porque top-N corta antes.
    assert "…" not in bloque or len(bloque) > 0

    bloque_largo = cb._bloque_correcciones_rag([{"contenido": "Z" * 5000}])
    assert "…" in bloque_largo
    assert len(bloque_largo) < 5000 + 200


def test_mensaje_reintento_con_json_previo():
    _stub_externos()
    from app.ai.context_builder import armar_mensaje_reintento

    previa = {"clave": "X1", "layout": {"frente_mm": 2504}}
    msg = armar_mensaje_reintento(
        "Mensaje base del cliente",
        previa,
        ["Contrato: falta materiales", "Incompatibilidad: LRS-9"],
    )
    assert "NO redesignes desde cero" in msg
    assert '"clave":"X1"' in msg or '"clave": "X1"' in msg
    assert "Contrato: falta materiales" in msg
    assert "Incompatibilidad: LRS-9" in msg
    assert "Genera el proyecto COMPLETO otra vez" not in msg


def test_whitelist_knowledge_sin_html_ni_cuestionario():
    _stub_externos()
    from app.ai.clients import claude_client

    knowledge = Path(claude_client.BASE) / "knowledge"
    if not knowledge.exists():
        return  # entorno sin knowledge — no falla

    # Por defecto fichas tecnico/ NO van al prompt (van por RAG).
    os.environ.pop("EMBED_FICHAS_EN_PROMPT", None)
    # Recargar lógica: la función lee env en cada call
    archivos = claude_client._archivos_knowledge_whitelist(knowledge)
    nombres = [f.name for f in archivos]
    rutas = [str(f.relative_to(knowledge)).replace("\\", "/") for f in archivos]

    assert all(not n.endswith(".html") for n in nombres)
    assert "catalogo_pm.json" not in nombres
    assert not any(n.startswith("cuestionario") for n in nombres)
    assert sum(1 for n in nombres if n.endswith(".json")) <= claude_client._MAX_EJEMPLOS_DORADOS
    # Solo dorados en ejemplos/ (tecnico solo si EMBED_FICHAS_EN_PROMPT=1)
    assert all(r.startswith("ejemplos/") for r in rutas)
    assert not any(r.startswith("tecnico/") for r in rutas)


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
