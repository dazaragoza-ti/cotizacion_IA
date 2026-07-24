"""Validador estructural de proyectos de rack PM La Piedad.

Verifica que el JSON del proyecto sea **fabricable**:
  - Códigos del despiece existen en el catálogo.
  - Combinaciones cabecera + larguero + cargador son válidas.
  - Frentes de larguero son los del catálogo (121/151/181/221/242/272/302 cm).
  - Cantidad de cargadores correcta según frente (2 para ≥272, 1 para ≤242).
  - Anclaje correcto según altura de cabecera (≥4025 mm → taquete 5/8" × 6").
  - Factor de seguridad ≥ 1.5 sobre la capacidad del marco.
  - Factor de seguridad ≥ 1.5 sobre la capacidad REAL del larguero elegido
    (varía 1300-6000 kg/par según su combinación frente+peralte específica,
    no solo contra el límite genérico del marco).
  - Despiece coherente (cantidades de cabeceras, largueros, cargadores, taquetes).

Devuelve:
  - errores: lista de problemas críticos (proyecto NO fabricable)
  - advertencias: cosas a revisar (proyecto fabricable pero con riesgo)
  - info: confirmaciones positivas

Las reglas vienen del catálogo PEME + criterio del usuario (Xocotzin).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.engineering.sku_diff import normalizar_sku

log = logging.getLogger("validador")

# ── Constantes del catálogo (fuente: catalogo_pm / RACKS-PEME.pdf) ───────────
FRENTES_LARGUERO_CATALOGO = [1294, 1594, 1894, 2294, 2504, 2804, 3104]   # mm
FRENTES_CON_2_CARGADORES = [2804, 3104]                                   # ≥ 272 cm
FONDOS_CABECERA_STOCK = [612, 917, 1232]                                  # 61, 91.5, 123 cm

ALTURAS_CABECERA_STOCK = [
    1226, 1530, 1834, 2240, 2443, 2748, 3001, 3357, 3665, 4025,           # mm
]
ALTURA_TAQUETE_GRANDE = 4025  # ≥ → MPR0833 obligatorio

CAP_MARCO_PESADA_INDIVIDUAL = 4500  # kg/sección individual
CAP_MARCO_LIGERA_INDIVIDUAL = 2500
FACTOR_SEGURIDAD_MIN = 1.5

# Peraltes válidos (mm × 10) — fuente: Presentacion_producto_Racks.pdf §LARGUEROS
PERALTES_PESADA = [100, 125, 150]   # 10 / 12.5 / 15 cm
PERALTES_LIGERA = [75]              # solo 7.5 cm

# Calibres válidos de entrepaño — fuente: Presentacion_producto_Racks.pdf §ENTREPAÑOS
CALIBRES_ENTREPANO_PESADA = [22, 18, 14]
CALIBRES_ENTREPANO_LIGERA = [22, 18]

# Calzas por cabecera — Presentacion_producto_Racks.pdf §CHECKLIST: "6 piezas por cabecera"
CALZAS_POR_CABECERA = 6

# Taquetes
TAQUETE_PEQUENO = "TEM-0019"   # 1/2" × 4½" (también MPR0313)
TAQUETE_PEQUENO_ALT = "MPR0313"
TAQUETE_GRANDE = "MPR0833"     # 5/8" × 6"

# Calzas
CALZA_PEQUENA = "CNP-7931"
CALZA_GRANDE = "RA0047"

# Tornillería obligatoria
TORNILLO_SEGURIDAD = "MPR0272"   # 5/16" × 3/4" alta resistencia (1 por ménsula)


# ── Resultado del validador ─────────────────────────────────────────────────
@dataclass
class ResultadoValidacion:
    errores: list[str] = field(default_factory=list)
    advertencias: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    @property
    def es_valido(self) -> bool:
        return not self.errores

    def resumen(self) -> str:
        partes = []
        if self.errores:
            partes.append("❌ " + str(len(self.errores)) + " error(es) crítico(s)")
        if self.advertencias:
            partes.append("⚠️ " + str(len(self.advertencias)) + " advertencia(s)")
        if not partes:
            partes.append("✅ Proyecto válido")
        return " · ".join(partes)

    def como_texto(self) -> str:
        out = ["## Validación estructural\n"]
        if self.errores:
            out.append("### ❌ Errores críticos (corregir antes de fabricar)\n")
            for e in self.errores:
                out.append(f"- {e}")
        if self.advertencias:
            out.append("\n### ⚠️ Advertencias (revisar)\n")
            for w in self.advertencias:
                out.append(f"- {w}")
        if self.info and not (self.errores or self.advertencias):
            out.append("\n### ✅ Validaciones superadas\n")
            for i in self.info[:6]:  # no saturar
                out.append(f"- {i}")
        return "\n".join(out)


# ── Carga del catálogo ──────────────────────────────────────────────────────
def _cargar_catalogo() -> list[dict]:
    """Misma fuente que Claude/compat/ventas: Supabase via consultar_catalogo_pm
    (con fallback al JSON local aplanado si la consulta falla).

    Import diferido para no acoplar el módulo a supabase cuando el caller
    ya inyecta el catálogo (tests / evaluacion / pipeline).
    """
    from app.services.catalogo_pm_service import consultar_catalogo_pm
    return consultar_catalogo_pm()


def _codigos_del_catalogo(catalogo: list[dict]) -> set[str]:
    """Códigos de pieza del catálogo plano (filas de catalogo_pm)."""
    codigos: set[str] = set()
    for fila in catalogo or []:
        codigo = fila.get("codigo")
        if isinstance(codigo, str) and codigo:
            codigos.add(codigo.upper())
    return codigos


# ── Helpers ─────────────────────────────────────────────────────────────────
def _es_carga_pesada(proyecto: dict) -> bool:
    """Determina si el proyecto es carga pesada (vs ligera)."""
    spec = (proyecto.get("especificacion") or "").lower()
    tipo_layout = ((proyecto.get("layout") or {}).get("tipo") or "").lower()
    memoria_tc = ((proyecto.get("memoria") or {}).get("tipo_carga") or "").lower()
    textos = " ".join([spec, tipo_layout, memoria_tc])
    if "ligera" in textos:
        return False
    return True  # default: pesada (es la más común)


def _codigo_base(codigo: str) -> str:
    """Quita sufijos de color (-AZ, -NA, -AC, -GA, -AM, etc.) del código.

    Delegado al normalizador único compartido con sku_diff.py (antes había dos
    regex idénticas mantenidas por separado — TODO(sprint2) resuelto: Fase 0/9).
    """
    return normalizar_sku(codigo)


def _contar_por_prefijo(materiales: list[dict], prefijo: str) -> int:
    """Suma pzas de todos los materiales cuyo código empiece con `prefijo`."""
    total = 0
    for m in materiales:
        cod = (m.get("codigo") or "").upper()
        if cod.startswith(prefijo.upper()):
            try:
                total += int(m.get("pzas") or 0)
            except (TypeError, ValueError):
                pass
    return total


def _hay_codigo(materiales: list[dict], codigos_buscar: list[str]) -> int:
    """Devuelve la suma de pzas para cualquiera de los códigos dados."""
    objetivo = {c.upper() for c in codigos_buscar}
    total = 0
    for m in materiales:
        cod = _codigo_base((m.get("codigo") or "").upper())
        if cod in objetivo or (m.get("codigo") or "").upper() in objetivo:
            try:
                total += int(m.get("pzas") or 0)
            except (TypeError, ValueError):
                pass
    return total


# ── Validaciones individuales ───────────────────────────────────────────────
def _v_layout(proyecto: dict, r: ResultadoValidacion) -> None:
    layout = proyecto.get("layout") or {}
    requeridas = ["modulos_x", "modulos_y", "frente_mm", "fondo_mm",
                  "pasillo_mm", "niveles", "altura_total_mm",
                  "peralte_larguero_mm"]
    faltantes = [k for k in requeridas if k not in layout]
    if faltantes:
        r.errores.append("Layout incompleto, faltan claves: " + ", ".join(faltantes))
        return

    frente = layout["frente_mm"]
    fondo = layout["fondo_mm"]
    altura = layout["altura_total_mm"]
    niveles = layout.get("niveles") or []

    if frente not in FRENTES_LARGUERO_CATALOGO:
        r.errores.append(
            f"Frente {frente} mm no está en catálogo. "
            f"Frentes válidos: {FRENTES_LARGUERO_CATALOGO} mm "
            f"(= 121/151/181/221/242/272/302 cm). "
            f"Elegir el más cercano de catálogo."
        )
    else:
        r.info.append(f"Frente {frente} mm es de catálogo ✓")

    if fondo not in FONDOS_CABECERA_STOCK:
        r.errores.append(
            f"Fondo de cabecera {fondo} mm NO es stock PM. "
            f"Stock disponible: 612 / 917 / 1232 mm (61 / 91.5 / 123 cm). "
            f"Cualquier otro es especial — sustituir."
        )
    else:
        r.info.append(f"Fondo {fondo} mm es stock ✓")

    if not niveles or niveles[0] != 0:
        r.errores.append(
            "La lista 'niveles' debe empezar en 0 (el piso). "
            "Ejemplo correcto: [0, 1800, 3600, 5400]."
        )

    # Cabecera disponible: la altura_total no puede exceder 4025 mm sin grapas
    if altura > 4025:
        if _hay_codigo(proyecto.get("materiales") or [], ["GR-7492", "RA0063"]) == 0:
            r.advertencias.append(
                f"altura_total_mm = {altura} mm excede la cabecera más alta "
                f"de catálogo (4025 mm). Necesita GRAPA UNIDORA de poste "
                f"(GR-7492 o RA0063) para apilar dos cabeceras. "
                f"No la veo en el despiece."
            )


def _v_peralte(proyecto: dict, r: ResultadoValidacion) -> None:
    """El peralte del larguero debe ser de catálogo según la familia.
    Fuente: Presentacion_producto_Racks.pdf §LARGUEROS.
    """
    layout = proyecto.get("layout") or {}
    peralte = layout.get("peralte_larguero_mm")
    if peralte is None:
        return
    pesada = _es_carga_pesada(proyecto)

    if pesada:
        if peralte not in PERALTES_PESADA:
            r.errores.append(
                f"Peralte de larguero {peralte} mm NO es de catálogo para carga "
                f"PESADA. Valores válidos: {PERALTES_PESADA} mm (10, 12.5, 15 cm). "
                f"El peralte mayor admite más carga; elige según la carga por nivel."
            )
        else:
            r.info.append(f"Peralte {peralte} mm es de catálogo para carga pesada ✓")
    else:
        if peralte not in PERALTES_LIGERA:
            r.errores.append(
                f"Peralte de larguero {peralte} mm NO existe en carga LIGERA. "
                f"En carga ligera SOLO hay peralte 75 mm (7.5 cm). Si necesitas "
                f"otro peralte, cambia a carga PESADA."
            )
        else:
            r.info.append(f"Peralte {peralte} mm es de catálogo para carga ligera ✓")


def _v_combinaciones(proyecto: dict, r: ResultadoValidacion) -> None:
    """Carga pesada vs ligera: códigos deben ser coherentes."""
    materiales = proyecto.get("materiales") or []
    pesada = _es_carga_pesada(proyecto)

    # Detecta familia desde los códigos: CRG = pesada, CRL = ligera (típico)
    codigos = [_codigo_base((m.get("codigo") or "").upper()) for m in materiales]
    tiene_crg = any(c.startswith("CRG-") for c in codigos)
    tiene_crl = any(c.startswith("CRL-") for c in codigos)
    tiene_lrs_lrc = any(c.startswith("LRS-") or c.startswith("LRC-") for c in codigos)
    tiene_lrl = any(c.startswith("LRL-") for c in codigos)

    if tiene_crg and tiene_crl:
        r.errores.append(
            "Despiece mezcla cabeceras carga PESADA (CRG-) y LIGERA (CRL-). "
            "No se pueden combinar: postes 73 mm vs 38 mm — geometrías distintas."
        )

    if pesada and tiene_crl:
        r.errores.append(
            "Proyecto declarado como carga PESADA pero el despiece usa "
            "cabeceras de carga LIGERA (CRL-)."
        )
    if not pesada and tiene_crg:
        r.errores.append(
            "Proyecto declarado como carga LIGERA pero el despiece usa "
            "cabeceras de carga PESADA (CRG-)."
        )
    if pesada and tiene_lrl:
        r.errores.append(
            "Carga PESADA con largueros LIGEROS (LRL-): incompatible. "
            "Usar LRS- (sin escalón) o LRC- (con escalón) carga pesada."
        )


def _v_carga_ligera_obligatorios(proyecto: dict, r: ResultadoValidacion) -> None:
    """Carga LIGERA: tensor unidor de larguero es OBLIGATORIO en todo ensamble.
    Fuente: Presentacion_producto_Racks.pdf §ACCESORIOS: 'Es obligatorio en todo ensamble'.
    Además: largueros de carga ligera SIEMPRE llevan escalón.
    """
    if _es_carga_pesada(proyecto):
        return  # solo aplica a carga ligera

    materiales = proyecto.get("materiales") or []
    layout = proyecto.get("layout") or {}
    modulos_x = layout.get("modulos_x") or 0
    modulos_y = layout.get("modulos_y") or 0
    niveles = layout.get("niveles") or [0]
    n_niveles_carga = max(0, len(niveles) - 1)
    n_pares_largueros = modulos_x * modulos_y * n_niveles_carga

    # Tensor unidor: prefijos típicos TEN- o accesorio RA00xx con palabra "TENSOR"
    tensores = _contar_por_prefijo(materiales, "TEN-")
    for m in materiales:
        desc = (m.get("descripcion") or "").upper()
        if tensores == 0 and "TENSOR" in desc:
            try:
                tensores += int(m.get("pzas") or 0)
            except (TypeError, ValueError):
                pass
    if n_pares_largueros > 0 and tensores < n_pares_largueros:
        r.errores.append(
            f"Carga LIGERA REQUIERE tensor unidor de larguero (OBLIGATORIO en "
            f"todo ensamble — Presentacion_producto_Racks.pdf §ACCESORIOS). "
            f"Esperados {n_pares_largueros} tensores (1 por par de largueros), "
            f"despiece tiene {tensores}."
        )


def _v_cargadores(proyecto: dict, r: ResultadoValidacion) -> None:
    """Frente ≥ 272 cm requiere 2 cargadores por par; frente ≤ 242 cm requiere 1."""
    layout = proyecto.get("layout") or {}
    materiales = proyecto.get("materiales") or []
    frente = layout.get("frente_mm", 0)
    modulos_x = layout.get("modulos_x") or 0
    modulos_y = layout.get("modulos_y") or 0
    niveles = layout.get("niveles") or [0]
    n_niveles_carga = max(0, len(niveles) - 1)  # quita el piso

    if not frente or not modulos_x or not modulos_y or n_niveles_carga == 0:
        return  # _v_layout ya alertó

    n_bays_total = modulos_x * modulos_y
    cargadores_por_par = 2 if frente in FRENTES_CON_2_CARGADORES else 1
    cargadores_esperados = n_bays_total * n_niveles_carga * cargadores_por_par

    cargadores_en_despiece = _contar_por_prefijo(materiales, "CA-")
    if cargadores_en_despiece == 0:
        # Solo carga pesada usa cargadores; ligera usa tensor (TEN-/RA0xxx)
        if _es_carga_pesada(proyecto):
            r.errores.append(
                f"Carga PESADA pero el despiece no tiene cargadores (CA-). "
                f"Se necesitan {cargadores_esperados} "
                f"({cargadores_por_par} por par × {n_bays_total} bays × "
                f"{n_niveles_carga} niveles)."
            )
        return

    # Validar cantidad
    if cargadores_en_despiece < cargadores_esperados:
        r.errores.append(
            f"Cargadores en despiece = {cargadores_en_despiece}, "
            f"se requieren {cargadores_esperados} "
            f"(frente {frente} mm → {cargadores_por_par} cargador(es) por par × "
            f"{n_bays_total} bays × {n_niveles_carga} niveles). "
            + (f"Frente ≥ 272 cm REQUIERE 2 cargadores por par."
               if cargadores_por_par == 2 else "")
        )
    elif cargadores_en_despiece > cargadores_esperados:
        r.advertencias.append(
            f"Cargadores en despiece ({cargadores_en_despiece}) > esperado "
            f"({cargadores_esperados}). Revisar — sobra material."
        )
    else:
        r.info.append(
            f"Cargadores: {cargadores_en_despiece} correctos "
            f"({cargadores_por_par} por par)"
        )


def _v_anclaje(proyecto: dict, r: ResultadoValidacion) -> None:
    """Cabecera ≥ 4025 mm requiere taquete 5/8" × 6"."""
    layout = proyecto.get("layout") or {}
    materiales = proyecto.get("materiales") or []
    altura_cabecera = layout.get("altura_total_mm", 0)

    grande = _hay_codigo(materiales, [TAQUETE_GRANDE])
    pequeno = _hay_codigo(materiales, [TAQUETE_PEQUENO, TAQUETE_PEQUENO_ALT])

    if altura_cabecera >= ALTURA_TAQUETE_GRANDE:
        if grande == 0:
            r.errores.append(
                f"Altura de cabecera = {altura_cabecera} mm ≥ 4025 mm. "
                f"REQUIERE taquete arpón 5/8\" × 6\" ({TAQUETE_GRANDE}). "
                f"El despiece solo tiene taquete 1/2\" × 4½\" — insuficiente para esta altura."
            )
        if pequeno > 0:
            r.advertencias.append(
                f"Despiece mezcla taquete pequeño (1/2\") y grande (5/8\") para "
                f"rack alto. Para cabecera {altura_cabecera} mm usar SOLO el grande."
            )
        # Calza grande
        if _hay_codigo(materiales, [CALZA_GRANDE]) == 0:
            r.advertencias.append(
                f"Rack alto ({altura_cabecera} mm) — falta calza nivelar 4+ "
                f"({CALZA_GRANDE}). Usar esta en lugar de {CALZA_PEQUENA}."
            )
    else:
        # Rack < 4 m: taquete pequeño basta
        if grande > 0:
            r.advertencias.append(
                f"Despiece tiene taquete grande ({TAQUETE_GRANDE}) pero la "
                f"cabecera es {altura_cabecera} mm (< 4025 mm). Con "
                f"{TAQUETE_PEQUENO} es suficiente — revisar."
            )
        if pequeno == 0:
            r.errores.append(
                f"Sin taquete de anclaje en el despiece. Para rack "
                f"{altura_cabecera} mm usar {TAQUETE_PEQUENO} "
                f"(arpón 1/2\" × 4½\")."
            )

    # Cantidad de taquetes: 4 por placa × 2 placas × n_cabeceras = 8 por cabecera
    n_cabeceras = _contar_por_prefijo(materiales, "CRG-") + _contar_por_prefijo(materiales, "CRL-")
    if n_cabeceras > 0:
        esperados = n_cabeceras * 8
        total = grande + pequeno
        if total > 0 and total < esperados * 0.9:  # tolerancia 10%
            r.advertencias.append(
                f"Taquetes totales = {total}, esperados ≈ {esperados} "
                f"(8 por cabecera × {n_cabeceras} cabeceras)."
            )

    # Calzas: 6 piezas por cabecera (fuente: Presentacion_producto_Racks.pdf §CHECKLIST)
    calzas = _hay_codigo(materiales,
                          [CALZA_PEQUENA, CALZA_GRANDE, "RA0059"])
    if n_cabeceras > 0:
        esperadas = n_cabeceras * CALZAS_POR_CABECERA
        if calzas == 0:
            r.errores.append(
                f"Sin calzas para nivelar piso. Se requieren {esperadas} "
                f"({CALZAS_POR_CABECERA} por cabecera × {n_cabeceras} cabeceras). "
                f"Códigos: CNP-7931 (estándar), RA0047 (rack >4 m), RA0059 (carga ligera)."
            )
        elif calzas < esperadas * 0.9:
            r.advertencias.append(
                f"Calzas en despiece = {calzas}, esperadas ≈ {esperadas} "
                f"({CALZAS_POR_CABECERA} por cabecera × {n_cabeceras} cabeceras — "
                f"PDF §CHECKLIST)."
            )


def _v_capacidad(proyecto: dict, r: ResultadoValidacion) -> None:
    """Carga del módulo no debe exceder cap_marco / FS_min."""
    memoria = proyecto.get("memoria") or {}
    pesada = _es_carga_pesada(proyecto)
    cap_marco = CAP_MARCO_PESADA_INDIVIDUAL if pesada else CAP_MARCO_LIGERA_INDIVIDUAL

    carga_modulo = memoria.get("carga_modulo_kg")
    if not carga_modulo:
        return  # sin memoria de carga, no se puede validar

    try:
        carga_modulo = float(carga_modulo)
    except (TypeError, ValueError):
        return

    cap_limite = cap_marco / FACTOR_SEGURIDAD_MIN
    fs_real = (cap_marco / carga_modulo) if carga_modulo > 0 else float("inf")

    if carga_modulo > cap_marco:
        r.errores.append(
            f"CARGA EXCEDIDA: carga_modulo = {carga_modulo:,.0f} kg > "
            f"cap_marco = {cap_marco:,.0f} kg "
            f"(carga {'PESADA' if pesada else 'LIGERA'} individual). "
            f"Opciones: (a) reducir niveles, (b) reducir peso por nivel, "
            f"(c) cotizar con poste doble especial."
        )
    elif carga_modulo > cap_limite:
        r.advertencias.append(
            f"Factor de seguridad bajo: FS = {fs_real:.2f} "
            f"(carga_modulo {carga_modulo:,.0f} kg vs cap_marco {cap_marco:,.0f} kg). "
            f"Mínimo recomendado FS ≥ {FACTOR_SEGURIDAD_MIN}. Considerar aumentar."
        )
    else:
        r.info.append(
            f"Factor de seguridad OK: FS = {fs_real:.2f} ≥ {FACTOR_SEGURIDAD_MIN}"
        )


def _mapa_capacidad_largueros(catalogo: list[dict]) -> dict[str, float]:
    """codigo -> carga_kg real del catálogo (capacidad de ESE larguero
    especifico segun su combinacion frente+peralte). Va de 1300 a 6000 kg
    por par segun el SKU -- muy distinto entre si.

    Acepta el formato plano de catalogo_pm (campo carga_kg) y, por
    compatibilidad con filas aplanadas del JSON local, tambien carga_par_kg.
    """
    mapa: dict[str, float] = {}
    for fila in catalogo or []:
        codigo = fila.get("codigo")
        if not codigo:
            continue
        categoria = (fila.get("categoria") or "").lower()
        cod_u = str(codigo).upper()
        es_larguero = (
            categoria == "larguero"
            or cod_u.startswith(("LRS-", "LRC-", "LRL-"))
        )
        if not es_larguero:
            continue
        carga = fila.get("carga_kg")
        if carga is None:
            carga = fila.get("carga_par_kg")
        if carga is not None:
            mapa[cod_u] = float(carga)
    return mapa


def _v_capacidad_larguero(proyecto: dict, r: ResultadoValidacion, catalogo: list[dict]) -> None:
    """_v_capacidad ya revisa la capacidad TOTAL del marco (4500 kg fijo),
    pero eso no dice nada sobre si el LARGUERO especifico elegido aguanta
    la carga por nivel: el catálogo tiene una carga_kg real por combinacion
    frente+peralte que va de 1300 a 6000 kg -- un larguero de frente
    3104mm/peralte 100mm (1300 kg/par) puede fallar aunque el marco en
    conjunto todavia tenga margen.
    """
    materiales = proyecto.get("materiales") or []
    memoria = proyecto.get("memoria") or {}
    carga_nivel = memoria.get("carga_nivel_kg")
    if not carga_nivel:
        return  # sin memoria de carga por nivel, no se puede validar

    try:
        carga_nivel = float(carga_nivel)
    except (TypeError, ValueError):
        return

    mapa_capacidad = _mapa_capacidad_largueros(catalogo)
    if not mapa_capacidad:
        return  # catálogo sin datos de largueros, no se puede validar

    codigos_vistos: set[str] = set()
    for m in materiales:
        cod_full = (m.get("codigo") or "").upper()
        if not cod_full or not cod_full.startswith(("LRS-", "LRC-")):
            continue
        codigos_vistos.add(cod_full)

    for codigo in sorted(codigos_vistos):
        capacidad = mapa_capacidad.get(codigo) or mapa_capacidad.get(_codigo_base(codigo).upper())
        if capacidad is None:
            continue  # SKU sin dato de capacidad (p.ej. LRC- con escalon, aun no cargado)

        if carga_nivel > capacidad:
            r.errores.append(
                f"CARGA EXCEDIDA EN LARGUERO {codigo}: soporta {capacidad:,.0f} kg "
                f"por par en esta combinación frente/peralte, pero el proyecto "
                f"pide {carga_nivel:,.0f} kg por nivel. Opciones: (a) usar un "
                f"peralte mayor para el mismo frente, (b) reducir el frente, "
                f"(c) reducir la carga por nivel."
            )
            continue

        fs = capacidad / carga_nivel if carga_nivel > 0 else float("inf")
        if fs < FACTOR_SEGURIDAD_MIN:
            r.advertencias.append(
                f"Factor de seguridad bajo para el larguero {codigo}: "
                f"FS = {fs:.2f} (carga_nivel {carga_nivel:,.0f} kg vs "
                f"capacidad real {capacidad:,.0f} kg/par de este SKU). "
                f"Mínimo recomendado FS ≥ {FACTOR_SEGURIDAD_MIN} — "
                f"considerar un peralte mayor."
            )
        else:
            r.info.append(
                f"Larguero {codigo}: capacidad real {capacidad:,.0f} kg/par "
                f"OK para carga_nivel {carga_nivel:,.0f} kg (FS = {fs:.2f})."
            )


def _v_defensas_nom006(proyecto: dict, r: ResultadoValidacion) -> None:
    """NOM-006-STPS-2023: si hay montacargas, defensas amarillas son obligatorias.
    Mínimo 2 por corrida (las esquinas del rack expuestas al pasillo).
    """
    memoria = proyecto.get("memoria") or {}
    layout = proyecto.get("layout") or {}
    materiales = proyecto.get("materiales") or []
    n_corridas = layout.get("modulos_y") or 0

    montacargas_txt = (memoria.get("montacargas") or "").lower()
    if not montacargas_txt or "patin" in montacargas_txt or "patín" in montacargas_txt:
        return  # sin montacargas o solo patín, NOM-006 no aplica con defensas

    defensas = _contar_por_prefijo(materiales, "DR-")
    minimo = max(2 * n_corridas, 2)

    if defensas == 0:
        r.errores.append(
            f"Proyecto con montacargas ({montacargas_txt[:40]}) pero SIN DEFENSAS "
            f"en el despiece. NOM-006-STPS-2023 las hace obligatorias "
            f"(amarillas ≥30 cm). Mínimo {minimo} (2 por corrida × {n_corridas} corridas)."
        )
    elif defensas < minimo:
        r.advertencias.append(
            f"Defensas en despiece = {defensas}, mínimo NOM-006 = {minimo} "
            f"(2 por corrida × {n_corridas} corridas). Si hay pasillo central, "
            f"agregar más en sus esquinas."
        )


def _v_almacenamiento_alimentos(proyecto: dict, r: ResultadoValidacion) -> None:
    """NOM-251-SSA1-2009: alimentos / harina / granos requieren mención explícita
    en observaciones (pintura horneable, superficie limpiable)."""
    memoria = proyecto.get("memoria") or {}
    desc_extras = " ".join([
        str(proyecto.get("especificacion") or ""),
        str((layout := proyecto.get("layout") or {}).get("tipo") or ""),
        str(memoria.get("tipo_carga") or ""),
        " ".join(str(o) for o in (proyecto.get("observaciones") or [])),
    ]).lower()

    KEYS_ALIMENTOS = ["harina", "alimento", "granel", "grano", "bebida",
                      "suplemento", "agroquimico", "agroquímico", "lácteo",
                      "lacteo", "cereal", "azúcar", "azucar"]
    es_alimento = any(k in desc_extras for k in KEYS_ALIMENTOS)
    if not es_alimento:
        return

    obs_text = " ".join(str(o) for o in (proyecto.get("observaciones") or [])).lower()
    cita_norma = "nom-251" in obs_text or "ssa1" in obs_text
    cita_horneable = "hornea" in obs_text or "epoxi" in obs_text
    cita_limpieza = "limpiab" in obs_text or "limpiez" in obs_text

    faltas = []
    if not cita_norma:
        faltas.append("NOM-251-SSA1-2009")
    if not cita_horneable:
        faltas.append("pintura horneable")
    if not cita_limpieza:
        faltas.append("superficie limpiable")
    if faltas:
        r.advertencias.append(
            f"Proyecto para alimento/granel pero observaciones NO mencionan: "
            f"{', '.join(faltas)}. La NOM-251 exige acabados sin poros, sin "
            f"cantos vivos en zonas de contacto, separación de productos de "
            f"limpieza. Agrégalo en observaciones."
        )


def _v_codigos_existen(proyecto: dict, r: ResultadoValidacion,
                        catalogo: list[dict]) -> None:
    """Avisa si hay códigos en el despiece que no están en el catálogo PM."""
    materiales = proyecto.get("materiales") or []
    codigos_cat = _codigos_del_catalogo(catalogo)
    if not codigos_cat:
        return  # sin catálogo cargado, no se puede validar

    desconocidos = set()
    for m in materiales:
        cod_full = (m.get("codigo") or "").upper()
        if not cod_full:
            continue
        cod_base = _codigo_base(cod_full)
        if cod_base.upper() not in codigos_cat and cod_full not in codigos_cat:
            desconocidos.add(cod_full)

    if desconocidos:
        r.advertencias.append(
            "Códigos no encontrados en catalogo_pm (verificar que "
            "existan o ampliar catálogo): " + ", ".join(sorted(desconocidos))
        )


def _v_tornillo_seguridad(proyecto: dict, r: ResultadoValidacion) -> None:
    """Cada larguero requiere 2 tornillos de seguridad MPR0272 (1 por ménsula)."""
    materiales = proyecto.get("materiales") or []
    largueros = (_contar_por_prefijo(materiales, "LRS-")
                 + _contar_por_prefijo(materiales, "LRC-")
                 + _contar_por_prefijo(materiales, "LRL-"))
    tornillos = _hay_codigo(materiales, [TORNILLO_SEGURIDAD])

    if largueros > 0 and tornillos == 0:
        r.errores.append(
            f"Sin tornillos de seguridad ({TORNILLO_SEGURIDAD}, 5/16\" × 3/4\"). "
            f"Cada larguero lleva 1 por ménsula = 2 por larguero. "
            f"Despiece tiene {largueros} largueros → ≥ {largueros * 2} tornillos requeridos."
        )
    elif largueros > 0 and tornillos < largueros * 2 * 0.9:  # tolerancia 10%
        r.advertencias.append(
            f"Tornillos de seguridad insuficientes: {tornillos} vs "
            f"{largueros * 2} esperados ({largueros} largueros × 2 ménsulas)."
        )


# ── Entry point ─────────────────────────────────────────────────────────────
def validar(
    proyecto: dict,
    catalogo: list[dict] | None = None,
) -> ResultadoValidacion:
    """Valida el JSON del proyecto. Devuelve ResultadoValidacion.

    `catalogo` es opcional: si el caller ya tiene el catálogo plano
    (p.ej. de consultar_catalogo_pm), pásalo para evitar un segundo fetch
    y mantener la misma snapshot que compatibility. Si es None, se carga
    aquí (Supabase con fallback JSON local).
    """
    r = ResultadoValidacion()
    if not isinstance(proyecto, dict):
        r.errores.append("El proyecto no es un objeto JSON válido.")
        return r

    if catalogo is None:
        catalogo = _cargar_catalogo()

    _v_layout(proyecto, r)
    _v_peralte(proyecto, r)
    _v_combinaciones(proyecto, r)
    _v_cargadores(proyecto, r)
    _v_carga_ligera_obligatorios(proyecto, r)
    _v_anclaje(proyecto, r)
    _v_capacidad(proyecto, r)
    _v_capacidad_larguero(proyecto, r, catalogo)
    _v_tornillo_seguridad(proyecto, r)
    _v_defensas_nom006(proyecto, r)
    _v_almacenamiento_alimentos(proyecto, r)
    _v_codigos_existen(proyecto, r, catalogo)

    return r


# ── CLI para probar el validador desde la terminal ──────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python validador.py <ruta_proyecto.json>")
        sys.exit(2)
    p = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    res = validar(p)
    print(res.resumen())
    print()
    print(res.como_texto())
    sys.exit(0 if res.es_valido else 1)
