"""
Generador 3D de proyectos de rack PM La Piedad — versión 2.

Construye un modelo 3D con proporciones reales del catálogo PM:
- Postes 73x73 mm (poste gota carga pesada)
- Largueros con peralte real (100/125/150 mm) y grosor de lámina
- X-bracing simétrica en cabecera
- Entrepaños visibles en cada nivel
- Cargadores delgados

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


def _box(x, y, z, dx, dy, dz, color):
    m = trimesh.creation.box(extents=[dx, dy, dz])
    m.apply_translation([x + dx / 2, y + dy / 2, z + dz / 2])
    m.visual.face_colors = [int(c * 255) for c in color]
    return m


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


POSTE = 73        # mm — dimensión real del poste gota carga pesada
PLACA = 100       # mm — placa base
PLACA_H = 10
DIAG_TH = 18      # mm — solera 1/8"x1" diagonal (~25mm visual)

# Frentes de larguero que requieren 2 cargadores por par en vez de 1 -- misma
# tabla exacta que validator_engine.FRENTES_CON_2_CARGADORES y
# adaptador_visor._FRENTES_CON_2_CARGADORES (antes este archivo usaba un
# umbral aproximado ">= 2700", que coincidia en la practica porque los
# frentes de catalogo saltan de 2504 a 2804 sin valores intermedios, pero
# quedaba inconsistente con la regla real documentada/validada).
FRENTES_CON_2_CARGADORES = (2804, 3104)


def construir_cabecera_pm(x0, y0, altura_mm, fondo_mm):
    """Cabecera PM: 2 postes verticales + X-bracing en zigzag + placas base.

    Origen (x0, y0): esquina inferior-izquierda de la cabecera.
    Postes alineados en X = x0 a x0+POSTE, separados en Y por fondo_mm.
    """
    meshes = []
    # Posición postes
    px = x0
    py1 = y0
    py2 = y0 + fondo_mm - POSTE

    # Postes verticales (azul)
    meshes.append(_box(px, py1, 0, POSTE, POSTE, altura_mm, COL_AZUL))
    meshes.append(_box(px, py2, 0, POSTE, POSTE, altura_mm, COL_AZUL))

    # Placas base (debajo de cada poste)
    pad = (PLACA - POSTE) / 2
    meshes.append(_box(px - pad, py1 - pad, -PLACA_H, PLACA, PLACA, PLACA_H, COL_PLACA))
    meshes.append(_box(px - pad, py2 - pad, -PLACA_H, PLACA, PLACA, PLACA_H, COL_PLACA))

    # Cross-bracing horizontal cada cierta altura (mejora estabilidad y look real)
    # Patrón típico PM: travesaños horizontales + diagonales en X cada ~60-80 cm
    n_paneles = max(3, int(altura_mm / 700))
    paso = altura_mm / n_paneles

    # Centros de los postes para conectar barras
    cx = px + POSTE / 2
    cy1 = py1 + POSTE / 2
    cy2 = py2 + POSTE / 2

    # Horizontales: en cada nivel del panel
    for i in range(n_paneles + 1):
        z = i * paso
        if 0 < z < altura_mm - 1:
            meshes.append(_bar((cx, cy1, z), (cx, cy2, z), DIAG_TH, COL_AZUL))

    # Diagonales: alternando \ y / por panel
    for i in range(n_paneles):
        z_bot = i * paso
        z_top = (i + 1) * paso
        if i % 2 == 0:
            # \
            meshes.append(_bar((cx, cy1, z_bot), (cx, cy2, z_top), DIAG_TH, COL_AZUL))
        else:
            # /
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


def construir_modulo(x0, y0, datos, con_entrepano=True):
    """Un módulo completo: 2 cabeceras + largueros + cargadores + entrepaños."""
    L = datos["layout"]
    frente = L["frente_mm"]
    fondo = L["fondo_mm"]
    altura = L["altura_total_mm"]
    niveles = L["niveles"]
    peralte = L.get("peralte_larguero_mm", 100)
    meshes = []

    # Cabecera izquierda en x=0
    meshes.extend(construir_cabecera_pm(x0, y0, altura, fondo))
    # Cabecera derecha en x=frente-POSTE
    meshes.extend(construir_cabecera_pm(x0 + frente - POSTE, y0, altura, fondo))

    # Largueros + cargadores + entrepaños por nivel (omitir nivel 0 = piso)
    larguero_x = x0 + POSTE
    larguero_w = frente - 2 * POSTE
    espesor_larg = 72
    for nivel_z in niveles[1:]:
        # Larguero frontal
        meshes.extend(construir_larguero(larguero_x, y0, nivel_z,
                                          larguero_w, peralte, espesor_larg))
        # Larguero trasero
        meshes.extend(construir_larguero(larguero_x, y0 + fondo - espesor_larg, nivel_z,
                                          larguero_w, peralte, espesor_larg))
        # Cargador(es): 1 si frente <=242, 2 si >=272 (según catálogo PM)
        n_cargs = 2 if frente in FRENTES_CON_2_CARGADORES else 1
        carg_z = nivel_z + peralte - 30
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
            ent_z = nivel_z + peralte - 5  # arriba del larguero
            ent_y = y0 + espesor_larg
            ent_fondo = fondo - 2 * espesor_larg
            meshes.extend(construir_entrepano(larguero_x, ent_y, ent_z,
                                                larguero_w, ent_fondo, peralte=8))
    return meshes


def construir_corrida(x0, y0, n_modulos, datos, con_entrepano=True):
    """Corrida de n módulos: las cabeceras intermedias se comparten."""
    L = datos["layout"]
    frente = L["frente_mm"]
    fondo = L["fondo_mm"]
    altura = L["altura_total_mm"]
    niveles = L["niveles"]
    peralte = L.get("peralte_larguero_mm", 100)
    espesor_larg = 72
    meshes = []

    # Cabeceras: n+1
    for i in range(n_modulos + 1):
        cx = x0 + i * (frente - POSTE)  # comparten poste con el siguiente
        meshes.extend(construir_cabecera_pm(cx, y0, altura, fondo))

    # Largueros, cargadores y entrepaños por cada bay
    for i in range(n_modulos):
        bx = x0 + i * (frente - POSTE) + POSTE
        bw = frente - 2 * POSTE
        for nivel_z in niveles[1:]:
            meshes.extend(construir_larguero(bx, y0, nivel_z, bw, peralte))
            meshes.extend(construir_larguero(bx, y0 + fondo - espesor_larg, nivel_z,
                                              bw, peralte))
            n_cargs = 2 if frente in FRENTES_CON_2_CARGADORES else 1
            carg_z = nivel_z + peralte - 30
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
                meshes.extend(construir_entrepano(bx, ent_y, nivel_z + peralte - 5,
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

def _render(scene_mesh, vista, titulo, salida):
    """Renderiza una vista con matplotlib 3D, proporciones reales."""
    vertices = scene_mesh.vertices
    faces = scene_mesh.faces
    colors = scene_mesh.visual.face_colors / 255.0
    mn = vertices.min(axis=0)
    mx = vertices.max(axis=0)
    rng = mx - mn

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
    fig.suptitle(titulo, fontsize=13, weight="bold", color="#303030", y=0.96)
    plt.subplots_adjust(left=0.01, right=0.99, top=0.93, bottom=0.01)
    fig.savefig(salida, dpi=140, bbox_inches="tight", facecolor="white",
                pad_inches=0.1)
    plt.close(fig)
    print(f"Render: {salida}")


def generar(datos_json_path, out_dir):
    with open(datos_json_path) as f:
        datos = json.load(f)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    vistas = out_dir / "vistas"
    vistas.mkdir(exist_ok=True)

    print("Construyendo modelo COMPLETO...")
    mesh_full = construir_proyecto(datos)
    print(f"  {len(mesh_full.vertices)} vert, {len(mesh_full.faces)} caras")

    # Exportar archivos del proyecto completo
    clave = datos['clave']
    obj_path = out_dir / f"{clave}.obj"
    dae_path = out_dir / f"{clave}.dae"
    glb_path = out_dir / f"{clave}.glb"
    mesh_full.export(str(obj_path))
    print(f"OBJ: {obj_path}")
    try:
        mesh_full.export(str(dae_path))
        print(f"DAE: {dae_path}")
    except Exception as e:
        print(f"DAE skip: {e}")
    mesh_full.export(str(glb_path))

    # Renders del proyecto completo (planta para overview)
    titulo = datos.get("proyecto", "PROYECTO")
    _render(mesh_full, "planta", f"{titulo} — Vista en planta general",
            vistas / "render_planta.png")

    # Sección representativa para perspectiva (mejor detalle)
    print("Sección representativa...")
    mesh_rep = construir_seccion_representativa(datos, n_corridas_rep=2,
                                                  mods_por_corrida_rep=4)
    print(f"  {len(mesh_rep.vertices)} vert, {len(mesh_rep.faces)} caras")
    mesh_rep.export(str(out_dir / f"{datos['clave']}_seccion.obj"))
    _render(mesh_rep, "perspectiva",
             f"{titulo} — Perspectiva (sección representativa)",
             vistas / "render_perspectiva.png")

    # Módulo único en detalle (con entrepaños visibles)
    print("Módulo de detalle...")
    detalle = trimesh.util.concatenate(construir_modulo(0, 0, datos,
                                                          con_entrepano=True))
    print(f"  {len(detalle.vertices)} vert, {len(detalle.faces)} caras")
    detalle.export(str(out_dir / f"{datos['clave']}_modulo.obj"))
    detalle.export(str(out_dir / f"{datos['clave']}_modulo.dae"))
    _render(detalle, "perspectiva",
             f"{titulo} — Detalle de un módulo",
             vistas / "render_modulo_detalle.png")
    _render(detalle, "frontal",
             f"{titulo} — Alzado frontal (módulo)",
             vistas / "render_frontal.png")
    _render(detalle, "lateral",
             f"{titulo} — Alzado lateral (módulo)",
             vistas / "render_lateral.png")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python modelo_3d.py datos.json salida_dir")
        sys.exit(1)
    generar(sys.argv[1], sys.argv[2])
