"""Tests de mensajes_entrega (Telegram)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.telegram.mensajes_entrega import (
    armar_detalle_validacion,
    armar_mensaje_entrega,
    armar_mensaje_qa_fallido,
    etiqueta_archivo,
    ordenar_archivos_entrega,
)


def test_etiqueta_renders_y_planos():
    assert etiqueta_archivo(Path("render_perspectiva.png")) == "Render perspectiva"
    assert etiqueta_archivo(Path("Planos_X.pdf")).startswith("Planos")
    assert "glb" in etiqueta_archivo(Path("FOO.glb")).lower()


def test_ordenar_archivos_entrega_prioridad():
    paths = [
        Path("render_lateral.png"),
        Path("Despiece_A.xlsx"),
        Path("Planos_A.pdf"),
        Path("A.glb"),
        Path("Cotizacion_A.pdf"),
        Path("render_perspectiva.png"),
    ]
    orden = [p.name for p in ordenar_archivos_entrega(paths)]
    assert orden[0].startswith("Planos_")
    assert orden[1].startswith("Cotizacion_")
    assert orden[2].startswith("Despiece_")
    assert orden[3].endswith(".glb")
    assert orden[-2:] == ["render_perspectiva.png", "render_lateral.png"] or \
        orden.index("render_perspectiva.png") < orden.index("render_lateral.png")


def test_armar_mensaje_entrega_ok_con_visor():
    partes = armar_mensaje_entrega(
        proyecto={"clave": "X1", "cliente": "Acme", "especificacion": "Rack selectivo carga pesada"},
        archivos=[Path("Planos_X1.pdf"), Path("render_perspectiva.png")],
        link_visor_3d="https://example.com/?session_id=1",
        errores=[],
        avisos=[],
    )
    texto = "\n".join(partes)
    assert "¡Listo!" in texto
    assert "Aquí tienes tu proyecto" in texto
    assert "X1" in texto
    assert "Acme" in texto
    assert "Visor 3D" in texto
    assert "Te mando estos archivos" in texto
    assert "Validación: todo en orden" in texto
    assert "Si algo no cuadra" in texto
    assert len(texto) < 4000


def test_armar_mensaje_entrega_con_errores():
    partes = armar_mensaje_entrega(
        proyecto={"clave": "X2", "layout": {"tipo": "Selectivo"}},
        archivos=[],
        link_visor_3d=None,
        errores=["Frente inválido"],
        avisos=["Pasillo corto"],
    )
    texto = "\n".join(partes)
    assert "error" in texto.lower() or "❌" in texto
    assert "regener" in texto.lower()
    assert "lo regeneramos" in texto.lower() or "dime el ajuste" in texto.lower()


def test_armar_mensaje_entrega_con_avisos():
    partes = armar_mensaje_entrega(
        proyecto={"clave": "X3", "cliente": "Beta"},
        archivos=[Path("Planos_X3.pdf")],
        link_visor_3d=None,
        errores=[],
        avisos=["Pasillo corto"],
    )
    texto = "\n".join(partes)
    assert "advertencia" in texto.lower()
    assert "cerrar con el cliente" in texto.lower()


def test_armar_detalle_validacion_vacio():
    assert armar_detalle_validacion([], []) == []
    assert armar_detalle_validacion(None, None) == []


def test_armar_detalle_validacion_contenido():
    partes = armar_detalle_validacion(["E1"], ["A1"])
    texto = "\n".join(partes)
    assert "E1" in texto and "A1" in texto
    assert "Advertencias (revisar)" in texto


def test_armar_mensaje_qa_fallido():
    partes = armar_mensaje_qa_fallido("Larguero cruza travesaño", regenerar=True)
    texto = "\n".join(partes)
    assert "calidad" in texto.lower() or "🔍" in texto
    assert "Noté posibles defectos" in texto
    assert "regener" in texto.lower()
    assert "describe" in texto.lower() or "arreglo" in texto.lower()
