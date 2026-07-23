"""Validador geométrico del render 3D — detecta colisiones/huecos entre
piezas directamente en las coordenadas del mesh (bounding boxes), sin
depender de visión.

Complementa a qa_visual_client.py (que solo "mira" imágenes ya generadas):
este valida la geometría real ANTES de que exista cualquier imagen, así que
detecta con precisión milimétrica defectos que qa_visual_client.py solo
puede detectar si el ángulo de cámara los deja ver. No corrige nada por sí
mismo — solo emite un reporte estructurado; la corrección del código en
modelo_3d.py la hace el agente que lo invoca (ver
backend/app/ai/prompts/corrector_3d.md).

Funciona reusando construir_modulo()/construir_cabecera_pm() de modelo_3d.py
directamente — esas funciones ya devuelven la lista de mallas individuales
ANTES de concatenarlas en una sola pieza (eso solo pasa en
construir_proyecto()), así que cada mesh conserva sus bounds reales.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field

import numpy as np
import trimesh

from . import modelo_3d as m3d

TOLERANCIA_MM = 2.0  # margen de fabricación/redondeo antes de reportar hueco u overlap


@dataclass
class Pieza:
    tipo: str
    mesh: trimesh.Trimesh

    @property
    def bounds(self) -> np.ndarray:
        return self.mesh.bounds  # [[xmin,ymin,zmin],[xmax,ymax,zmax]]


@dataclass
class Defecto:
    regla: str
    descripcion: str
    severidad: str  # "baja" | "media" | "alta"
    detalle: dict = field(default_factory=dict)


def _color_de(mesh: trimesh.Trimesh) -> tuple:
    return tuple(mesh.visual.face_colors[0][:3])


def _es_poste(mesh: trimesh.Trimesh) -> bool:
    """Un poste es una caja: dos extents ~= POSTE (73mm), una extent grande (altura)."""
    dx, dy, dz = mesh.bounds[1] - mesh.bounds[0]
    extents_chicas = sum(1 for e in (dx, dy, dz) if abs(e - m3d.POSTE) < 5)
    return extents_chicas >= 2


def _clasificar(meshes: list[trimesh.Trimesh]) -> list[Pieza]:
    azul = tuple(int(c * 255) for c in m3d.COL_AZUL[:3])
    naranja = tuple(int(c * 255) for c in m3d.COL_NARANJA[:3])
    gris = tuple(int(c * 255) for c in m3d.COL_GRIS[:3])
    entrepano = tuple(int(c * 255) for c in m3d.COL_ENTREPANO[:3])
    placa = tuple(int(c * 255) for c in m3d.COL_PLACA[:3])

    piezas = []
    for mesh in meshes:
        color = _color_de(mesh)
        if color == azul:
            tipo = "poste" if _es_poste(mesh) else "travesano"
        elif color == naranja:
            tipo = "larguero"
        elif color == gris:
            tipo = "cargador"
        elif color == entrepano:
            tipo = "entrepano"
        elif color == placa:
            tipo = "placa"
        else:
            tipo = "desconocido"
        piezas.append(Pieza(tipo=tipo, mesh=mesh))
    return piezas


def _overlap_1d(a0: float, a1: float, b0: float, b1: float) -> float:
    """Longitud del traslape en un eje; negativo = hueco (separación)."""
    return min(a1, b1) - max(a0, b0)


def _regla_larguero_vs_travesano_intermedio(piezas: list[Pieza]) -> list[Defecto]:
    """Regla 1 de renderizador.md: un larguero nunca debe caer dentro de la
    banda intermedia del travesaño del marco (defecto ya corregido una vez
    en modelo_3d.py -- este check evita que reaparezca)."""
    defectos = []
    largueros = [p for p in piezas if p.tipo == "larguero"]
    travesanos = [p for p in piezas if p.tipo == "travesano"]
    if not travesanos:
        return defectos

    z_travesanos = sorted({round((t.bounds[0][2] + t.bounds[1][2]) / 2, 1) for t in travesanos})
    if len(z_travesanos) < 3:
        return defectos  # sin banda "intermedia" identificable (menos de 3 niveles de travesaño)
    z_intermedios = z_travesanos[1:-1]  # excluye banda inferior y superior (correctas por diseño)

    for larg in largueros:
        lz0, lz1 = larg.bounds[0][2], larg.bounds[1][2]
        lx0, lx1 = larg.bounds[0][0], larg.bounds[1][0]
        for t in travesanos:
            tz = (t.bounds[0][2] + t.bounds[1][2]) / 2
            if not any(abs(tz - zi) < 1 for zi in z_intermedios):
                continue
            tx0, tx1 = t.bounds[0][0], t.bounds[1][0]
            if _overlap_1d(lx0, lx1, tx0, tx1) <= 0:
                continue  # no comparten X, es un travesaño de otra cabecera
            if lz0 - TOLERANCIA_MM < tz < lz1 + TOLERANCIA_MM:
                defectos.append(Defecto(
                    regla="larguero_vs_travesano_intermedio",
                    descripcion=(
                        f"Larguero en z=[{lz0:.0f},{lz1:.0f}] cruza el travesaño "
                        f"intermedio del marco en z={tz:.0f}"
                    ),
                    severidad="alta",
                    detalle={"larguero_z": [lz0, lz1], "travesano_z": tz},
                ))
    return defectos


def _regla_placa_bajo_poste(piezas: list[Pieza]) -> list[Defecto]:
    """Regla 5: cada poste debe tener una placa tocando el piso justo debajo."""
    defectos = []
    postes = [p for p in piezas if p.tipo == "poste"]
    placas = [p for p in piezas if p.tipo == "placa"]

    for poste in postes:
        px0, py0 = poste.bounds[0][0], poste.bounds[0][1]
        px1, py1 = poste.bounds[1][0], poste.bounds[1][1]
        tiene_placa = False
        for placa in placas:
            cx = (placa.bounds[0][0] + placa.bounds[1][0]) / 2
            cy = (placa.bounds[0][1] + placa.bounds[1][1]) / 2
            if px0 - 10 <= cx <= px1 + 10 and py0 - 10 <= cy <= py1 + 10:
                if abs(placa.bounds[1][2] - poste.bounds[0][2]) < TOLERANCIA_MM:
                    tiene_placa = True
                    break
        if not tiene_placa:
            defectos.append(Defecto(
                regla="placa_bajo_poste",
                descripcion=f"Poste en x=[{px0:.0f},{px1:.0f}] y=[{py0:.0f},{py1:.0f}] sin placa base debajo",
                severidad="alta",
                detalle={"poste_bounds": poste.bounds.tolist()},
            ))
    return defectos


def _regla_larguero_extremos(piezas: list[Pieza]) -> list[Defecto]:
    """Regla 2: el larguero debe llegar exacto de marco a marco.

    Convención real del código (validada contra adaptador_visor.py, ver
    comentarios en construir_modulo/construir_corrida): frente_mm es la
    distancia entre los ORÍGENES de los postes, no entre sus caras internas.
    El larguero por eso arranca flush con el origen (cara externa) del poste
    izquierdo -- envolviéndolo, donde va el gancho integrado -- y termina
    flush con el origen (cara cercana) del poste derecho. Este check valida
    esa alineación exacta, no un espacio simétrico entre caras internas."""
    defectos = []
    largueros = [p for p in piezas if p.tipo == "larguero"]
    postes = [p for p in piezas if p.tipo == "poste"]
    if not postes:
        return defectos

    for larg in largueros:
        lx0, lx1 = larg.bounds[0][0], larg.bounds[1][0]
        ly0, ly1 = larg.bounds[0][1], larg.bounds[1][1]
        # postes cuya banda Y se solapa con el larguero (mismo lado, frontal o trasero)
        candidatos = [p for p in postes if _overlap_1d(ly0, ly1, p.bounds[0][1], p.bounds[1][1]) > 0]
        # poste izquierdo: su origen (min-x) coincide con el arranque del larguero
        izq = [p for p in candidatos if abs(p.bounds[0][0] - lx0) < TOLERANCIA_MM]
        # poste derecho: su origen (min-x) coincide con el final del larguero
        der = [p for p in candidatos if abs(p.bounds[0][0] - lx1) < TOLERANCIA_MM]
        if not izq and not der:
            continue  # no se encontró ningún poste de referencia (ej. orilla de corrida) -- no evaluable
        if not izq:
            defectos.append(Defecto(
                regla="larguero_extremo",
                descripcion=f"Larguero x=[{lx0:.0f},{lx1:.0f}] no arranca flush con el origen de ningún poste izquierdo",
                severidad="media",
                detalle={"larguero_x0": lx0},
            ))
        if not der:
            defectos.append(Defecto(
                regla="larguero_extremo",
                descripcion=f"Larguero x=[{lx0:.0f},{lx1:.0f}] no termina flush con el origen de ningún poste derecho",
                severidad="media",
                detalle={"larguero_x1": lx1},
            ))
    return defectos


def _regla_cargador_apoyado(piezas: list[Pieza]) -> list[Defecto]:
    """Regla 6: el cargador cruza de larguero frontal a trasero, unido a
    ambos por su cara -- no debe flotar (sin tocar ningún larguero en Y) ni
    quedar fuera del rango de altura del larguero en Z. El cargador SÍ se
    embebe unos mm dentro de la altura del larguero por diseño (queda unido
    a su cara interna, no apoyado encima) -- basta con que su rango Z se
    traslape con el del larguero, no que coincida con su tope."""
    defectos = []
    cargadores = [p for p in piezas if p.tipo == "cargador"]
    largueros = [p for p in piezas if p.tipo == "larguero"]
    for carg in cargadores:
        cx0, cx1 = carg.bounds[0][0], carg.bounds[1][0]
        cy0, cy1 = carg.bounds[0][1], carg.bounds[1][1]
        cz0, cz1 = carg.bounds[0][2], carg.bounds[1][2]
        toca_algun_larguero = False
        for larg in largueros:
            if _overlap_1d(cx0, cx1, larg.bounds[0][0], larg.bounds[1][0]) <= 0:
                continue
            # el cargador y el larguero solo se TOCAN en Y (borde a borde), no se solapan
            if _overlap_1d(cy0, cy1, larg.bounds[0][1], larg.bounds[1][1]) < -TOLERANCIA_MM:
                continue
            if _overlap_1d(cz0, cz1, larg.bounds[0][2], larg.bounds[1][2]) <= 0:
                continue
            toca_algun_larguero = True
            break
        if not toca_algun_larguero:
            defectos.append(Defecto(
                regla="cargador_apoyado",
                descripcion=f"Cargador en z=[{cz0:.0f},{cz1:.0f}] no toca ningún larguero cercano en su rango de altura",
                severidad="media",
                detalle={"cargador_z": [cz0, cz1]},
            ))
    return defectos


REGLAS = [
    _regla_larguero_vs_travesano_intermedio,
    _regla_placa_bajo_poste,
    _regla_larguero_extremos,
    _regla_cargador_apoyado,
]


def validar_modulo(datos: dict) -> dict:
    """Corre todas las reglas geométricas sobre un módulo aislado (2 marcos).
    Devuelve {"ok": bool, "defectos": [...]}, mismo shape que
    qa_visual_client.revisar_render() para que el llamador los trate igual."""
    meshes = m3d.construir_modulo(0, 0, datos, con_entrepano=True)
    piezas = _clasificar(meshes)

    defectos: list[Defecto] = []
    for regla in REGLAS:
        defectos.extend(regla(piezas))

    return {
        "ok": len(defectos) == 0,
        "defectos": [
            {"regla": d.regla, "descripcion": d.descripcion, "severidad": d.severidad, "detalle": d.detalle}
            for d in defectos
        ],
    }


def validar_corrida(datos: dict, n_modulos: int = 3) -> dict:
    """Misma validación pero sobre una corrida de varios bays (para detectar
    defectos que solo aparecen cuando se comparten marcos intermedios)."""
    meshes = m3d.construir_corrida(0, 0, n_modulos, datos, con_entrepano=True)
    piezas = _clasificar(meshes)

    defectos: list[Defecto] = []
    for regla in REGLAS:
        defectos.extend(regla(piezas))

    return {
        "ok": len(defectos) == 0,
        "defectos": [
            {"regla": d.regla, "descripcion": d.descripcion, "severidad": d.severidad, "detalle": d.detalle}
            for d in defectos
        ],
    }


if __name__ == "__main__":
    # Uso: python -m app.ai.generators.validador_geometria <datos.json> [--corrida N]
    if len(sys.argv) < 2:
        print("Uso: python -m app.ai.generators.validador_geometria <datos.json> [--corrida N]", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        datos = json.load(f)
    if "--corrida" in sys.argv:
        n = int(sys.argv[sys.argv.index("--corrida") + 1])
        reporte = validar_corrida(datos, n_modulos=n)
    else:
        reporte = validar_modulo(datos)
    print(json.dumps(reporte, indent=2, ensure_ascii=False))
    sys.exit(0 if reporte["ok"] else 2)
