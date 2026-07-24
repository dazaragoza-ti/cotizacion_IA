"""
Generador 3D de proyectos de rack PM La Piedad — versión 2.

Construye un modelo 3D con proporciones reales del catálogo PM:
- Postes 73x73 mm (carga pesada) o 38x38 mm (carga ligera)
- Largueros con peralte real (100/125/150 mm) y grosor de lámina
- X-bracing simétrica en cabecera
- Entrepaños visibles en cada nivel
- Cargadores (solo carga pesada; ligera usa tensores en catálogo)
- Cantilever: columnas + brazos horizontales (geometría simplificada usable)
- Entrepiso: columnas + vigas + deck de piso (geometría simplificada usable)

Exporta OBJ, DAE (COLLADA, importable directo en SketchUp) y GLB,
más renders ortográficos e isométrico desde matplotlib.
"""

import json
import sys
from pathlib import Path

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

# Colores PM La Piedad (RGB normalizado)
COL_AZUL = (0.05, 0.32, 0.78, 1.0)
COL_NARANJA = (0.95, 0.40, 0.05, 1.0)
COL_GRIS = (0.45, 0.45, 0.48, 1.0)
COL_ENTREPANO = (0.85, 0.45, 0.20, 1.0)  # naranja más claro
COL_PLACA = (0.20, 0.20, 0.22, 1.0)
COL_SUELO = (0.92, 0.93, 0.94, 1.0)
COL_BRAZO = (0.90, 0.55, 0.10, 1.0)
COL_DECK = (0.70, 0.72, 0.75, 1.0)


def _box(x, y, z, dx, dy, dz, color):
    m = trimesh.creation.box(extents=[dx, dy, dz])
    m.apply_translation([x + dx / 2, y + dy / 2, z + dz / 2])
    m.visual.face_colors = [int(c * 255) for c in color]
    return m


def _mesh_para_glb(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Este generador construye todo en Z-arriba (Z = altura del rack), pero
    el formato glTF/GLB exige convencion Y-arriba -- sin esta conversion,
    cualquier visor glTF estricto (model-viewer del dashboard, Three.js
    GLTFLoader) muestra el rack "acostado"/rotado 90 grados, con piezas que
    deberian ser verticales viendose como si flotaran en diagonal. Se aplica
    SOLO al GLB; OBJ/DAE se quedan en Z-arriba (SketchUp los espera asi)."""
    convertido = mesh.copy()
    rotacion = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
    convertido.apply_transform(rotacion)
    return convertido


def _bar(p0, p1, thickness, color):
    """Barra cilíndrica de p0 a p1."""
    p0 = np.array(p0, float)
    p1 = np.array(p1, float)
    length = np.linalg.norm(p1 - p0)
    cyl = trimesh.creation.cylinder(radius=thickness / 2, height=length, sections=6)
    direction = (p1 - p0) / length
    z = np.array([0, 0, 1.0])
    if not np.allclose(direction, z):
        axis = np.cross(z, direction)
        n = np.linalg.norm(axis)
        if n > 1e-6:
            axis = axis / n
            angle = np.arccos(np.clip(np.dot(z, direction), -1, 1))
            cyl.apply_transform(trimesh.transformations.rotation_matrix(angle, axis))
    cyl.apply_translation((p0 + p1) / 2)
    cyl.visual.face_colors = [int(c * 255) for c in color]
    return cyl


POSTE_PESADA = 73   # mm — poste gota carga pesada
POSTE_LIGERA = 38   # mm — poste gota carga ligera
POSTE = POSTE_PESADA  # alias compat (validador / callers externos)
PLACA_PESADA = 100
PLACA_LIGERA = 70
PLACA = PLACA_PESADA
PLACA_H = 10
DIAG_TH = 18      # mm — solera 1/8"x1" diagonal (~25mm visual)

# Frentes de larguero que requieren 2 cargadores por par en vez de 1 -- misma
# tabla exacta que validator_engine.FRENTES_CON_2_CARGADORES y
# adaptador_visor._FRENTES_CON_2_CARGADORES (antes este archivo usaba un
# umbral aproximado ">= 2700", que coincidia en la practica porque los
# frentes de catalogo saltan de 2504 a 2804 sin valores intermedios, pero
# quedaba inconsistente con la regla real documentada/validada).
FRENTES_CON_2_CARGADORES = (2804, 3104)

TIPOS_CANTILEVER = ("cantilever",)
TIPOS_ENTREPISO = ("entrepiso", "mezzanine", "mezanine", "mezzanín")


def es_carga_ligera(datos: dict) -> bool:
    """True si especificación/memoria indican carga ligera gota."""
    spec = (datos.get("especificacion") or "").lower()
    tipo_layout = ((datos.get("layout") or {}).get("tipo") or "").lower()
    memoria_tc = ((datos.get("memoria") or {}).get("tipo_carga") or "").lower()
    return "ligera" in " ".join([spec, tipo_layout, memoria_tc])


def poste_mm_de(datos: dict) -> int:
    return POSTE_LIGERA if es_carga_ligera(datos) else POSTE_PESADA


def tipo_sistema(datos: dict) -> str:
    return str((datos.get("layout") or {}).get("tipo") or "Selectivo")


def _tipo_lower(datos: dict) -> str:
    return tipo_sistema(datos).lower()


def es_cantilever(datos: dict) -> bool:
    t = _tipo_lower(datos)
    return any(k in t for k in TIPOS_CANTILEVER)


def es_entrepiso(datos: dict) -> bool:
    t = _tipo_lower(datos)
    return any(k in t for k in TIPOS_ENTREPISO)


def geometria_selectiva_soportada(datos: dict) -> bool:
    """True si el generador produce mesh (selectivo, cantilever o entrepiso)."""
    return True  # todos los tipos tipados tienen geometría (simplificada o completa)


def familia_geometria(datos: dict) -> str:
    if es_cantilever(datos):
        return "cantilever"
    if es_entrepiso(datos):
        return "entrepiso"
    return "selectivo"


def construir_cabecera_pm(x0, y0, altura_mm, fondo_mm, niveles=None, peralte_mm=0,
                          poste_mm=None):
    """Cabecera PM: 2 postes verticales + X-bracing en zigzag + placas base.

    Origen (x0, y0): esquina inferior-izquierda de la cabecera.
    Postes alineados en X = x0 a x0+poste, separados en Y por fondo_mm.

    `niveles`/`peralte_mm`: alturas de carga y peralte del larguero. Se usan
    para anclar el enrejado a los niveles y evitar que una banda del marco
    caiga dentro de un larguero (ver más abajo).
    """
    poste = POSTE if poste_mm is None else int(poste_mm)
    placa = PLACA_LIGERA if poste <= POSTE_LIGERA + 2 else PLACA_PESADA
    meshes = []
    # Posición postes
    px = x0
    py1 = y0
    py2 = y0 + fondo_mm - poste

    # Postes verticales (azul)
    meshes.append(_box(px, py1, 0, poste, poste, altura_mm, COL_AZUL))
    meshes.append(_box(px, py2, 0, poste, poste, altura_mm, COL_AZUL))

    # Placas base (debajo de cada poste)
    pad = (placa - poste) / 2
    meshes.append(_box(px - pad, py1 - pad, -PLACA_H, placa, placa, PLACA_H, COL_PLACA))
    meshes.append(_box(px - pad, py2 - pad, -PLACA_H, placa, placa, PLACA_H, COL_PLACA))

    # Centros de los postes para conectar barras
    cx = px + poste / 2
    cy1 = py1 + poste / 2
    cy2 = py2 + poste / 2

    # Cross-bracing (travesaños horizontales + diagonales en zigzag).
    #
    # Los vértices del enrejado se ANCLAN a los niveles de carga en vez de
    # repartirse uniformemente por la altura. Antes los nodos caían en
    # i*altura/n_paneles, ignorando dónde van los largueros; cuando una banda
    # (o el punto medio de una diagonal, que es lo que "ve" el validador como
    # un travesaño a esa altura) coincidía con un nivel, se cruzaba con el
    # larguero -- viola la regla 1 de renderizador.md y lo detectan tanto el
    # QA visual como validador_geometria. Al usar los niveles como vértices,
    # el punto medio de cada diagonal cae SIEMPRE en el hueco entre dos
    # largueros (nunca dentro del peralte de uno). El espaciado de la ficha
    # técnica (§6, "aproximadamente cada 60-80 cm") es una guía, no una cota
    # rígida, así que los huecos altos se subdividen para no alejarse de
    # ~700 mm de panel.
    niveles = niveles or [0, altura_mm]
    puntos = sorted({0.0, float(altura_mm)}
                    | {float(z) for z in niveles if 0 < z < altura_mm})
    nodos = []
    for a, b in zip(puntos[:-1], puntos[1:]):
        n_sub = max(1, round((b - a) / 700))
        for j in range(n_sub):
            nodos.append(a + j * (b - a) / n_sub)
    nodos.append(float(altura_mm))
    nodos = sorted(set(nodos))

    # Bandas ocupadas por el peralte de cada larguero (el larguero cuelga de
    # nivel_z hacia abajo: z = [nivel - peralte, nivel]).
    bandas = [(z - peralte_mm, z) for z in niveles if 0 < z <= altura_mm]

    def _choca_larguero(z):
        return any(b0 - DIAG_TH < z < b1 + DIAG_TH for b0, b1 in bandas)

    # Horizontales: base y tope SIEMPRE (el kit real trae banda superior e
    # inferior soldadas de fábrica, además de las intermedias); los nodos
    # intermedios sólo si no chocan con el peralte de un larguero.
    for z in nodos:
        if z <= 0 or z >= altura_mm - 1e-6 or not _choca_larguero(z):
            meshes.append(_bar((cx, cy1, z), (cx, cy2, z), DIAG_TH, COL_AZUL))

    # Diagonales: alternando \ y / entre nodos consecutivos.
    for i, (z_bot, z_top) in enumerate(zip(nodos[:-1], nodos[1:])):
        if i % 2 == 0:
            meshes.append(_bar((cx, cy1, z_bot), (cx, cy2, z_top), DIAG_TH, COL_AZUL))
        else:
            meshes.append(_bar((cx, cy2, z_bot), (cx, cy1, z_top), DIAG_TH, COL_AZUL))

    return meshes


def construir_larguero(x0, y0, z0, frente_mm, peralte_mm, espesor=72):
    """Larguero C-channel horizontal entre dos postes.

    x0, y0, z0: esquina inferior del larguero (entre postes, cara frontal).
    frente_mm: longitud útil del larguero (de poste a poste).
    peralte_mm: altura del larguero (100/125/150 mm según catálogo).
    """
    # Larguero como caja delgada (mejor visualmente que C-channel sin más detalle)
    return [_box(x0, y0, z0, frente_mm, espesor, peralte_mm, COL_NARANJA)]


def construir_cargador(x0, y0, z0, fondo_util, ancho=60, espesor=30):
    """Cargador: barra horizontal que une larguero frontal y trasero."""
    return [_box(x0, y0, z0, ancho, fondo_util, espesor, COL_GRIS)]


def construir_entrepano(x0, y0, z0, frente, fondo, peralte=40):
    """Entrepaño cal 22: superficie horizontal sobre el escalón del larguero."""
    return [_box(x0, y0, z0, frente, fondo, peralte, COL_ENTREPANO)]


def construir_columna_cantilever(x0, y0, altura_mm, poste_mm=None):
    """Columna vertical + placa base (cantilever)."""
    poste = POSTE if poste_mm is None else int(poste_mm)
    placa = PLACA_LIGERA if poste <= POSTE_LIGERA + 2 else PLACA_PESADA
    meshes = []
    meshes.append(_box(x0, y0, 0, poste, poste, altura_mm, COL_AZUL))
    pad = (placa - poste) / 2
    meshes.append(_box(x0 - pad, y0 - pad, -PLACA_H, placa, placa, PLACA_H, COL_PLACA))
    return meshes


def construir_brazo_cantilever(x0, y0, z0, largo_mm, ancho_mm=80, alto_mm=60):
    """Brazo horizontal que sale de la columna en +Y (lado de carga)."""
    return [_box(x0, y0, z0, ancho_mm, largo_mm, alto_mm, COL_BRAZO)]


def construir_modulo_cantilever(x0, y0, datos):
    """Módulo cantilever simplificado: 2 columnas + brazos a cada nivel.

    Convención layout:
      - frente_mm = separación entre columnas (eje X)
      - fondo_mm = largo del brazo (proyección en Y)
      - niveles = alturas de brazos (incluye 0 = piso)
    """
    L = datos["layout"]
    frente = L["frente_mm"]
    fondo = L["fondo_mm"]
    altura = L["altura_total_mm"]
    niveles = L.get("niveles") or [0, altura]
    poste = poste_mm_de(datos)
    meshes = []

    meshes.extend(construir_columna_cantilever(x0, y0, altura, poste_mm=poste))
    meshes.extend(construir_columna_cantilever(x0 + frente, y0, altura, poste_mm=poste))

    for z in (altura * 0.35, altura * 0.7, max(poste, altura - 40)):
        meshes.append(_bar(
            (x0 + poste / 2, y0 + poste / 2, z),
            (x0 + frente + poste / 2, y0 + poste / 2, z),
            DIAG_TH, COL_AZUL,
        ))

    brazo_w = max(50, poste)
    for nivel_z in niveles[1:]:
        z0 = max(0, nivel_z - 60)
        meshes.extend(construir_brazo_cantilever(
            x0 + (poste - brazo_w) / 2, y0 + poste, z0, fondo, brazo_w, 60,
        ))
        meshes.extend(construir_brazo_cantilever(
            x0 + frente + (poste - brazo_w) / 2, y0 + poste, z0, fondo, brazo_w, 60,
        ))
    return meshes


def construir_corrida_cantilever(x0, y0, n_modulos, datos):
    L = datos["layout"]
    frente = L["frente_mm"]
    meshes = []
    for i in range(n_modulos):
        meshes.extend(construir_modulo_cantilever(x0 + i * frente, y0, datos))
    return meshes


def construir_modulo_entrepiso(x0, y0, datos):
    """Entrepiso simplificado: 4 columnas + vigas perimetrales + deck."""
    L = datos["layout"]
    frente = float(L["frente_mm"])
    fondo = float(L["fondo_mm"])
    altura = float(L["altura_total_mm"])
    niveles = L.get("niveles") or [0, altura]
    poste = max(80, poste_mm_de(datos) + 20)
    meshes = []

    for dx, dy in ((0, 0), (frente, 0), (0, fondo), (frente, fondo)):
        meshes.append(_box(x0 + dx, y0 + dy, 0, poste, poste, altura, COL_AZUL))
        pad = 15
        meshes.append(_box(
            x0 + dx - pad, y0 + dy - pad, -PLACA_H,
            poste + 2 * pad, poste + 2 * pad, PLACA_H, COL_PLACA,
        ))

    viga_h = 120
    viga_t = 60
    decks = [z for z in niveles if z > 0] or [altura]
    for z_deck in decks:
        z_viga = max(0, z_deck - viga_h)
        meshes.append(_box(x0, y0, z_viga, frente + poste, viga_t, viga_h, COL_NARANJA))
        meshes.append(_box(x0, y0 + fondo, z_viga, frente + poste, viga_t, viga_h, COL_NARANJA))
        meshes.append(_box(x0, y0, z_viga, viga_t, fondo + poste, viga_h, COL_NARANJA))
        meshes.append(_box(x0 + frente, y0, z_viga, viga_t, fondo + poste, viga_h, COL_NARANJA))
        paso = 1500
        n_int = max(0, int(frente // paso))
        for i in range(1, n_int + 1):
            xi = x0 + i * (frente / (n_int + 1))
            meshes.append(_box(xi, y0, z_viga, viga_t, fondo + poste, viga_h, COL_GRIS))
        deck_th = 40
        meshes.append(_box(
            x0 + viga_t, y0 + viga_t, z_deck - deck_th,
            max(100, frente - viga_t), max(100, fondo - viga_t),
            deck_th, COL_DECK,
        ))
    return meshes


def construir_corrida_entrepiso(x0, y0, n_modulos, datos):
    L = datos["layout"]
    frente = L["frente_mm"]
    meshes = []
    for i in range(n_modulos):
        meshes.extend(construir_modulo_entrepiso(x0 + i * frente, y0, datos))
    return meshes


def construir_modulo(x0, y0, datos, con_entrepano=True):
    """Un módulo completo según familia (selectivo / cantilever / entrepiso)."""
    fam = familia_geometria(datos)
    if fam == "cantilever":
        return construir_modulo_cantilever(x0, y0, datos)
    if fam == "entrepiso":
        return construir_modulo_entrepiso(x0, y0, datos)

    L = datos["layout"]
    frente = L["frente_mm"]
    fondo = L["fondo_mm"]
    altura = L["altura_total_mm"]
    niveles = L["niveles"]
    peralte = L.get("peralte_larguero_mm", 100)
    poste = poste_mm_de(datos)
    ligera = es_carga_ligera(datos)
    meshes = []

    # Cabecera izquierda en x=0
    meshes.extend(construir_cabecera_pm(x0, y0, altura, fondo, niveles, peralte,
                                        poste_mm=poste))
    # Cabecera derecha en x=frente -- frente_mm es la distancia real entre
    # postes (coincide con la longitud del larguero de catalogo, ej. "LARGUERO
    # 1894MM"), misma convencion que ya usa adaptador_visor.py para el visor
    # web. Antes se restaba POSTE aqui, dejando el modulo ~73mm mas angosto
    # de lo real (y el error se acumulaba por cada bay en una corrida).
    meshes.extend(construir_cabecera_pm(x0 + frente, y0, altura, fondo, niveles,
                                        peralte, poste_mm=poste))

    # Largueros + cargadores + entrepaños por nivel (omitir nivel 0 = piso)
    # nivel_z es la altura de la superficie de carga (donde se apoya la
    # tarima) -- el larguero se construye COLGANDO de ahí hacia abajo
    # (z0 = nivel_z - peralte, tope en nivel_z), no empezando en nivel_z y
    # sobresaliendo hacia arriba como una mesa encima de los postes (defecto
    # que el QA visual detectó comparando contra el kit de referencia real).
    larguero_x = x0
    larguero_w = frente
    # Visual: larguero ~poste en profundidad; ligera es más delgado
    espesor_larg = max(40, poste - 1) if ligera else 72
    for nivel_z in niveles[1:]:
        larguero_z0 = nivel_z - peralte
        # Larguero frontal
        meshes.extend(construir_larguero(larguero_x, y0, larguero_z0,
                                          larguero_w, peralte, espesor_larg))
        # Larguero trasero
        meshes.extend(construir_larguero(larguero_x, y0 + fondo - espesor_larg, larguero_z0,
                                          larguero_w, peralte, espesor_larg))
        # Cargadores solo en carga pesada (ligera usa tensores en catálogo)
        if not ligera:
            n_cargs = 2 if frente in FRENTES_CON_2_CARGADORES else 1
            carg_z = nivel_z - 30
            carg_y = y0 + espesor_larg
            carg_fondo_util = fondo - 2 * espesor_larg
            if n_cargs == 1:
                cx = x0 + frente / 2 - 30
                meshes.extend(construir_cargador(cx, carg_y, carg_z, carg_fondo_util))
            else:
                for fr in [0.30, 0.70]:
                    cx = x0 + frente * fr - 30
                    meshes.extend(construir_cargador(cx, carg_y, carg_z, carg_fondo_util))

        # Entrepaño: superficie sobre el larguero (escalón)
        if con_entrepano:
            ent_z = nivel_z - 5  # arriba del larguero
            ent_y = y0 + espesor_larg
            ent_fondo = fondo - 2 * espesor_larg
            meshes.extend(construir_entrepano(larguero_x, ent_y, ent_z,
                                                larguero_w, ent_fondo, peralte=8))
    return meshes


def construir_corrida(x0, y0, n_modulos, datos, con_entrepano=True):
    """Corrida de n módulos según familia geométrica."""
    fam = familia_geometria(datos)
    if fam == "cantilever":
        return construir_corrida_cantilever(x0, y0, n_modulos, datos)
    if fam == "entrepiso":
        return construir_corrida_entrepiso(x0, y0, n_modulos, datos)

    L = datos["layout"]
    frente = L["frente_mm"]
    fondo = L["fondo_mm"]
    altura = L["altura_total_mm"]
    niveles = L["niveles"]
    peralte = L.get("peralte_larguero_mm", 100)
    poste = poste_mm_de(datos)
    ligera = es_carga_ligera(datos)
    espesor_larg = max(40, poste - 1) if ligera else 72
    meshes = []

    # Cabeceras: n+1, espaciadas exactamente frente_mm (misma convencion que
    # adaptador_visor.py -- antes se restaba POSTE, acumulando ~73mm de error
    # por cada bay adicional en corridas largas).
    for i in range(n_modulos + 1):
        cx = x0 + i * frente
        meshes.extend(construir_cabecera_pm(cx, y0, altura, fondo, niveles, peralte,
                                            poste_mm=poste))

    # Largueros, cargadores y entrepaños por cada bay -- nivel_z es la altura
    # de la superficie de carga, el larguero cuelga de ahí hacia abajo
    # (mismo fix que construir_modulo, ver ahí el porqué).
    for i in range(n_modulos):
        bx = x0 + i * frente
        bw = frente
        for nivel_z in niveles[1:]:
            larguero_z0 = nivel_z - peralte
            meshes.extend(construir_larguero(bx, y0, larguero_z0, bw, peralte, espesor_larg))
            meshes.extend(construir_larguero(bx, y0 + fondo - espesor_larg, larguero_z0,
                                              bw, peralte, espesor_larg))
            if not ligera:
                n_cargs = 2 if frente in FRENTES_CON_2_CARGADORES else 1
                carg_z = nivel_z - 30
                carg_y = y0 + espesor_larg
                carg_fondo_util = fondo - 2 * espesor_larg
                if n_cargs == 1:
                    meshes.extend(construir_cargador(bx + bw / 2 - 30, carg_y, carg_z,
                                                      carg_fondo_util))
                else:
                    for fr in [0.30, 0.70]:
                        meshes.extend(construir_cargador(bx + bw * fr - 30, carg_y, carg_z,
                                                          carg_fondo_util))
            if con_entrepano:
                ent_y = y0 + espesor_larg
                ent_fondo = fondo - 2 * espesor_larg
                meshes.extend(construir_entrepano(bx, ent_y, nivel_z - 5,
                                                    bw, ent_fondo, peralte=8))
    return meshes


def construir_proyecto(datos, max_modulos_render=120):
    """Modelo del proyecto completo (con TODOS los módulos)."""
    L = datos["layout"]
    fondo = L["fondo_mm"]
    pasillo = L.get("pasillo_mm", 1200)
    if "zones" in L:
        n_corridas = len(L["zones"])
        mods_por_corrida = L["zones"][0].get("modulos", 1)
    else:
        n_corridas = L.get("modulos_y", 4)
        mods_por_corrida = L.get("modulos_x", 6)

    meshes = []
    for j in range(n_corridas):
        y = j * (fondo + pasillo)
        meshes.extend(construir_corrida(0, y, mods_por_corrida, datos,
                                          con_entrepano=False))
    return trimesh.util.concatenate(meshes)


def construir_seccion_representativa(datos, n_corridas_rep=2, mods_por_corrida_rep=4):
    """Sección representativa para render: pocas corridas y módulos, MÁS DETALLE."""
    L = datos["layout"]
    fondo = L["fondo_mm"]
    pasillo = L.get("pasillo_mm", 1200)
    meshes = []
    for j in range(n_corridas_rep):
        y = j * (fondo + pasillo)
        meshes.extend(construir_corrida(0, y, mods_por_corrida_rep, datos,
                                          con_entrepano=True))
    return trimesh.util.concatenate(meshes)


# ============= RENDERS =============

def _meta_dims(datos: dict) -> dict:
    L = datos.get("layout") or {}
    return {
        "frente": L.get("frente_mm"),
        "fondo": L.get("fondo_mm"),
        "altura": L.get("altura_total_mm"),
        "pasillo": L.get("pasillo_mm"),
        "niveles": L.get("niveles") or [],
        "poste": poste_mm_de(datos),
        "tipo": tipo_sistema(datos),
        "carga": (datos.get("memoria") or {}).get("tipo_carga")
                 or ("Carga ligera gota" if es_carga_ligera(datos) else "Carga pesada gota"),
        "clave": datos.get("clave", ""),
    }


def _pie_info(meta: dict) -> str:
    partes = [
        f"Poste {meta['poste']} mm",
        f"{meta['carga']}",
        f"Tipo: {meta['tipo']}",
    ]
    if meta.get("frente"):
        partes.append(f"Frente {meta['frente']} mm")
    if meta.get("fondo"):
        partes.append(f"Fondo {meta['fondo']} mm")
    if meta.get("altura"):
        partes.append(f"Altura {meta['altura']} mm")
    n_niv = max(0, len(meta.get("niveles") or []) - 1)
    if n_niv:
        partes.append(f"{n_niv} nivel(es)")
    return "  ·  ".join(partes)


def _render_stub(salida, titulo: str, mensaje: str, meta: dict | None = None):
    """PNG honesto cuando no hay geometría real (cantilever/entrepiso)."""
    fig, ax = plt.subplots(figsize=(11, 7.5), dpi=140, facecolor="white")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(plt.Rectangle((0.08, 0.22), 0.84, 0.55,
                                fill=True, facecolor="#FFF5F5",
                                edgecolor="#B00020", linewidth=1.5))
    ax.text(0.5, 0.62, titulo, ha="center", va="center",
            fontsize=14, weight="bold", color="#303030", wrap=True)
    ax.text(0.5, 0.48, mensaje, ha="center", va="center",
            fontsize=11, color="#B00020", wrap=True)
    if meta:
        ax.text(0.5, 0.12, _pie_info(meta), ha="center", va="center",
                fontsize=8, color="#505050")
    fig.savefig(salida, dpi=140, bbox_inches="tight", facecolor="white",
                pad_inches=0.15)
    plt.close(fig)
    print(f"Stub render: {salida}")


def _render(scene_mesh, vista, titulo, salida, meta: dict | None = None):
    """Renderiza una vista con matplotlib 3D, proporciones reales + pie informativo."""
    vertices = scene_mesh.vertices
    faces = scene_mesh.faces
    colors = scene_mesh.visual.face_colors / 255.0
    mn = vertices.min(axis=0)
    mx = vertices.max(axis=0)
    rng = mx - mn
    # Evitar división por cero en geometrías degeneradas
    rng = np.where(rng < 1e-3, 1.0, rng)

    if vista == "perspectiva":
        w, h = 11, 7.5
    elif vista == "frontal":
        w, h = max(8, rng[0] / 800), max(5, rng[2] / 400)
    elif vista == "lateral":
        w, h = max(6, rng[1] / 400), max(5, rng[2] / 400)
    elif vista == "planta":
        w, h = max(10, rng[0] / 600), max(7, rng[1] / 600)
    else:
        w, h = 10, 7
    w = min(w, 18); h = min(h, 13)

    fig = plt.figure(figsize=(w, h), dpi=140, facecolor="white")
    ax = fig.add_subplot(111, projection="3d")
    # Iluminación: shade faces by normal Y component
    normals = scene_mesh.face_normals
    shade = 0.65 + 0.35 * (normals[:, 2] * 0.4 + normals[:, 0] * 0.4 + 0.3)
    shade = np.clip(shade, 0.4, 1.0)
    shaded_colors = colors.copy()
    shaded_colors[:, :3] = shaded_colors[:, :3] * shade[:, None]

    poly = Poly3DCollection(vertices[faces], facecolors=shaded_colors,
                            edgecolors=(0, 0, 0, 0.12), linewidths=0.15)
    ax.add_collection3d(poly)

    # Suelo de referencia (claridad de escala / apoyo visual)
    suelo_z = mn[2] - max(5.0, rng[2] * 0.01)
    sx0, sx1 = mn[0] - rng[0] * 0.02, mx[0] + rng[0] * 0.02
    sy0, sy1 = mn[1] - rng[1] * 0.02, mx[1] + rng[1] * 0.02
    suelo = [
        [[sx0, sy0, suelo_z], [sx1, sy0, suelo_z],
         [sx1, sy1, suelo_z], [sx0, sy1, suelo_z]]
    ]
    ax.add_collection3d(Poly3DCollection(
        suelo, facecolors=[COL_SUELO], edgecolors=(0.7, 0.7, 0.72, 0.4),
        linewidths=0.3, alpha=0.55))

    pad = 0.03
    ax.set_xlim(mn[0] - rng[0] * pad, mx[0] + rng[0] * pad)
    ax.set_ylim(mn[1] - rng[1] * pad, mx[1] + rng[1] * pad)
    ax.set_zlim(mn[2] - rng[2] * pad, mx[2] + rng[2] * pad)
    ax.set_box_aspect([rng[0], rng[1], rng[2]])

    if vista == "perspectiva":
        ax.view_init(elev=25, azim=-55)
    elif vista == "frontal":
        ax.view_init(elev=0, azim=-90)
    elif vista == "lateral":
        ax.view_init(elev=0, azim=0)
    elif vista == "planta":
        ax.view_init(elev=89.9, azim=-90)

    ax.set_axis_off()
    fig.suptitle(titulo, fontsize=13, weight="bold", color="#303030", y=0.97)

    # Leyenda de colores + cotas clave (2D, legible)
    leyenda = "Azul=poste/marco  ·  Naranja=larguero  ·  Gris=cargador  ·  Terracota=entrepaño"
    fig.text(0.5, 0.035, leyenda, ha="center", fontsize=7.5, color="#505050")
    if meta:
        fig.text(0.5, 0.012, _pie_info(meta), ha="center", fontsize=8,
                 color="#202020", weight="bold")
        # Escala aproximada (bbox mayor dimensión)
        mayor = float(max(rng))
        fig.text(0.98, 0.97, f"Escala aprox. bbox {mayor/1000:.2f} m",
                 ha="right", va="top", fontsize=7, color="#707070")

    plt.subplots_adjust(left=0.01, right=0.99, top=0.92, bottom=0.07)
    fig.savefig(salida, dpi=140, bbox_inches="tight", facecolor="white",
                pad_inches=0.12)
    plt.close(fig)
    print(f"Render: {salida}")


def _generar_stubs_no_soportado(datos, vistas: Path):
    """5 PNG con aviso cuando el tipo no es selectivo."""
    meta = _meta_dims(datos)
    tipo = meta["tipo"]
    titulo_base = datos.get("proyecto") or datos.get("clave") or "PROYECTO"
    msg = (
        f"Geometría 3D no disponible para «{tipo}».\n"
        "Este generador modela solo rack SELECTIVO (pesada/ligera).\n"
        "Cantilever / entrepiso: stub honesto — no se inventa geometría."
    )
    stubs = [
        ("render_planta.png", f"{titulo_base} — Planta (stub)"),
        ("render_perspectiva.png", f"{titulo_base} — Perspectiva (stub)"),
        ("render_modulo_detalle.png", f"{titulo_base} — Detalle (stub)"),
        ("render_frontal.png", f"{titulo_base} — Alzado frontal (stub)"),
        ("render_lateral.png", f"{titulo_base} — Alzado lateral (stub)"),
    ]
    for nombre, tit in stubs:
        _render_stub(vistas / nombre, tit, msg, meta)
    aviso = vistas / "AVISO_GEOMETRIA.txt"
    aviso.write_text(
        f"Tipo de sistema: {tipo}\n"
        "Limitación: modelo_3d.py solo genera geometría real para Selectivo.\n"
        "Los PNG son stubs informativos.\n",
        encoding="utf-8",
    )
    print(f"AVISO: geometría no soportada para tipo={tipo}. Stubs en {vistas}")


def generar(datos_json_path, out_dir):
    with open(datos_json_path, encoding="utf-8") as f:
        datos = json.load(f)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vistas = out_dir / "vistas"
    vistas.mkdir(exist_ok=True)

    clave = datos.get("clave") or "PROYECTO"
    titulo = datos.get("proyecto") or clave
    meta = _meta_dims(datos)
    fam = familia_geometria(datos)

    if fam != "selectivo":
        aviso = vistas / "AVISO_GEOMETRIA.txt"
        aviso.write_text(
            f"Tipo: {meta['tipo']} (familia={fam})\n"
            "Geometría 3D SIMPLIFICADA usable (no catálogo GLB de piezas reales).\n"
            "Úsala para proporciones y layout; no para fabricación millimétrica.\n",
            encoding="utf-8",
        )

    print(f"Construyendo modelo COMPLETO ({fam}, poste {meta['poste']} mm, {meta['carga']})...")
    mesh_full = construir_proyecto(datos)
    print(f"  {len(mesh_full.vertices)} vert, {len(mesh_full.faces)} caras")

    # Exportar archivos del proyecto completo
    obj_path = out_dir / f"{clave}.obj"
    dae_path = out_dir / f"{clave}.dae"
    glb_path = out_dir / f"{clave}.glb"
    try:
        mesh_full.export(str(obj_path))
        print(f"OBJ: {obj_path}")
    except Exception as e:
        print(f"OBJ skip: {e}")
    try:
        mesh_full.export(str(dae_path))
        print(f"DAE: {dae_path}")
    except Exception as e:
        print(f"DAE skip: {e}")
    try:
        _mesh_para_glb(mesh_full).export(str(glb_path))
        print(f"GLB: {glb_path}")
    except Exception as e:
        print(f"GLB skip: {e}")

    # Renders del proyecto completo (planta para overview)
    _render(mesh_full, "planta", f"{titulo} — Vista en planta general",
            vistas / "render_planta.png", meta=meta)

    # Sección representativa para perspectiva (mejor detalle)
    print("Sección representativa...")
    mesh_rep = construir_seccion_representativa(datos, n_corridas_rep=2,
                                                  mods_por_corrida_rep=4)
    print(f"  {len(mesh_rep.vertices)} vert, {len(mesh_rep.faces)} caras")
    mesh_rep.export(str(out_dir / f"{clave}_seccion.obj"))
    _render(mesh_rep, "perspectiva",
             f"{titulo} — Perspectiva (sección representativa)",
             vistas / "render_perspectiva.png", meta=meta)

    # Módulo único en detalle (con entrepaños visibles)
    print("Módulo de detalle...")
    detalle = trimesh.util.concatenate(construir_modulo(0, 0, datos,
                                                          con_entrepano=True))
    print(f"  {len(detalle.vertices)} vert, {len(detalle.faces)} caras")
    detalle.export(str(out_dir / f"{clave}_modulo.obj"))
    try:
        detalle.export(str(out_dir / f"{clave}_modulo.dae"))
    except Exception as e:
        print(f"DAE modulo skip: {e}")
    _render(detalle, "perspectiva",
             f"{titulo} — Detalle de un módulo",
             vistas / "render_modulo_detalle.png", meta=meta)
    _render(detalle, "frontal",
             f"{titulo} — Alzado frontal (módulo)",
             vistas / "render_frontal.png", meta=meta)
    _render(detalle, "lateral",
             f"{titulo} — Alzado lateral (módulo)",
             vistas / "render_lateral.png", meta=meta)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python modelo_3d.py datos.json salida_dir")
        sys.exit(1)
    generar(sys.argv[1], sys.argv[2])
