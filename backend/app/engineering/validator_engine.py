"""Validador estructural de proyectos de rack PM La Piedad.

Verifica que el JSON del proyecto sea **fabricable**:
  - Códigos del despiece existen en el catálogo.
  - Combinaciones cabecera + larguero + cargador son válidas.
  - Frentes de larguero son los del catálogo (121/151/181/221/242/272/302 cm).
  - Cantidad de cargadores correcta según frente (2 para ≥272, 1 para ≤242).
  - Anclaje correcto según altura de cabecera (≥4025 mm → taquete 5/8" × 6").
  - Factor de seguridad ≥ 1.5 sobre la capacidad del marco.
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
import re
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("validador")
BASE = Path(__file__).resolve().parent
CATALOGO_PATH = BASE / "knowledge" / "catalogo_pm.json"

# ── Constantes del catálogo (fuente: catalogo_pm.json + RACKS-PEME.pdf) ─────
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
def _cargar_catalogo() -> dict:
    if not CATALOGO_PATH.exists():
        log.warning("catalogo_pm.json no encontrado en %s", CATALOGO_PATH)
        return {}
    try:
        return json.loads(CATALOGO_PATH.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.exception("no se pudo leer catalogo_pm.json: %s", e)
        return {}


def _codigos_del_catalogo(catalogo: dict) -> set[str]:
    """Extrae todos los códigos de pieza del catálogo (recursivo)."""
    codigos: set[str] = set()

    def _walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "codigo" and isinstance(v, str):
                    codigos.add(v)
                else:
                    _walk(v)
        elif isinstance(obj, list):
            for x in obj:
                _walk(x)

    _walk(catalogo)
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
    """Quita sufijos de color (-AZ, -NA, -AC, -GA, -AM, etc.) del código."""
    if not codigo:
        return ""
    # Sufijos típicos: 2-3 letras al final separados por guion
    return re.sub(r"-(AZ|NA|AC|GA|AM|VR|GR|BL|RJ)$", "", codigo, flags=re.IGNORECASE)


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
                        catalogo: dict) -> None:
    """Avisa si hay códigos en el despiece que no están en catalogo_pm.json."""
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
            "Códigos no encontrados en catalogo_pm.json (verificar que "
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
def validar(proyecto: dict) -> ResultadoValidacion:
    """Valida el JSON del proyecto. Devuelve ResultadoValidacion."""
    r = ResultadoValidacion()
    if not isinstance(proyecto, dict):
        r.errores.append("El proyecto no es un objeto JSON válido.")
        return r

    catalogo = _cargar_catalogo()

    _v_layout(proyecto, r)
    _v_peralte(proyecto, r)
    _v_combinaciones(proyecto, r)
    _v_cargadores(proyecto, r)
    _v_carga_ligera_obligatorios(proyecto, r)
    _v_anclaje(proyecto, r)
    _v_capacidad(proyecto, r)
    _v_tornillo_seguridad(proyecto, r)
    _v_defensas_nom006(proyecto, r)
    _v_almacenamiento_alimentos(proyecto, r)
    _v_codigos_existen(proyecto, r, catalogo)

    return r

def validar_proyecto_pm(datos: dict) -> list[str]:
    """
    Recorre las reglas estructurales OBLIGATORIAS del proyectista PM.
    Devuelve una lista de errores; vacía = el proyecto puede fabricarse.
    """
    errores: list[str] = []
    layout = datos.get("layout", {}) or {}
    materiales = datos.get("materiales", []) or []
    memoria = datos.get("memoria", {}) or {}
    especificacion = datos.get("especificacion", "") or ""
    pesada = _es_pesada(especificacion)
    ligera = _es_ligera(especificacion)

    if not pesada and not ligera:
        errores.append(
            f"especificacion='{especificacion}' no deja claro si es carga PESADA o LIGERA "
            "(debe contener una de esas dos palabras)."
        )

    # --- Frente ---
    frente = layout.get("frente_mm")
    if frente not in FRENTES_VALIDOS:
        errores.append(f"frente_mm={frente} no es un valor de stock válido {sorted(FRENTES_VALIDOS)}.")

    # --- Fondo ---
    fondo = layout.get("fondo_mm")
    if fondo not in FONDOS_VALIDOS:
        errores.append(f"fondo_mm={fondo} no está en stock {sorted(FONDOS_VALIDOS)}.")

    # --- Peralte ---
    peralte = layout.get("peralte_larguero_mm")
    if pesada and peralte not in PERALTES_PESADA:
        errores.append(f"peralte_larguero_mm={peralte} inválido para carga PESADA {sorted(PERALTES_PESADA)}.")
    if ligera and peralte != PERALTE_LIGERA:
        errores.append(f"peralte_larguero_mm={peralte} inválido para carga LIGERA (debe ser {PERALTE_LIGERA}mm).")

    # --- Niveles / altura total ---
    niveles = layout.get("niveles") or []
    altura_total = layout.get("altura_total_mm")
    if not niveles:
        errores.append("layout.niveles está vacío.")
    else:
        if niveles[0] != 0:
            errores.append("niveles debe empezar en 0 (piso).")
        if any(niveles[i] >= niveles[i + 1] for i in range(len(niveles) - 1)):
            errores.append("niveles debe ser estrictamente creciente.")
        if altura_total is not None and max(niveles) > altura_total:
            errores.append(f"El nivel más alto ({max(niveles)}mm) excede altura_total_mm ({altura_total}mm).")

        # Altura de cabecera de catálogo: inmediatamente superior a la altura útil.
        altura_util = max(niveles)
        if altura_util <= ALTURAS_CABECERA_CATALOGO[-1]:
            candidatas = [a for a in ALTURAS_CABECERA_CATALOGO if a >= altura_util]
            if candidatas and altura_total is not None and altura_total not in ALTURAS_CABECERA_CATALOGO:
                errores.append(
                    f"altura_total_mm={altura_total} no es una altura de cabecera de catálogo "
                    f"{ALTURAS_CABECERA_CATALOGO}. Debería ser {min(candidatas)}mm "
                    f"(inmediatamente superior a la altura útil {altura_util}mm)."
                )
        else:
            # Requiere apilar 2 cabeceras con grapa unidora poste.
            grapa_esperada = "GR-7492" if pesada else "RA0063"
            if not any(m.get("codigo") == grapa_esperada for m in materiales):
                errores.append(
                    f"altura_util={altura_util}mm > {ALTURAS_CABECERA_CATALOGO[-1]}mm: se requiere apilar "
                    f"dos cabeceras con grapa unidora poste ('{grapa_esperada}') en el despiece."
                )

    n_bays = layout.get("modulos_x") or 0
    n_corridas = layout.get("modulos_y") or 0
    n_niveles_usables = max(len(niveles) - 1, 0)
    n_cabeceras = n_corridas * (n_bays + 1)

    # --- Cargadores (solo carga pesada) ---
    if pesada and frente is not None:
        cargadores_por_par = 2 if frente >= 2804 else 1
        cargadores_esperados = n_bays * n_niveles_usables * cargadores_por_par
        cargadores_en_despiece = sum(
            m.get("pzas", 0) for m in materiales
            if (m.get("codigo") or "").upper().startswith("CRD") or "cargador" in (m.get("descripcion") or "").lower()
        )
        if cargadores_esperados > 0 and cargadores_en_despiece != cargadores_esperados:
            errores.append(
                f"Cargadores en despiece ({cargadores_en_despiece}) no coincide con lo esperado "
                f"({cargadores_esperados} = {n_bays} bays × {n_niveles_usables} niveles × "
                f"{cargadores_por_par} cargador(es)/par, por frente={frente}mm)."
            )

    # --- Anclaje: taquetes y calzas ---
    altura_max_cabecera = max(niveles) if niveles else 0
    usa_taquete_grande = altura_max_cabecera >= 4025 or (altura_total or 0) >= 4025
    codigo_taquete_esperado = "MPR0833" if usa_taquete_grande else ("TEM-0019", "MPR0313")
    tiene_taquete = any(
        (m.get("codigo") == codigo_taquete_esperado) if isinstance(codigo_taquete_esperado, str)
        else (m.get("codigo") in codigo_taquete_esperado)
        for m in materiales
    )
    if n_cabeceras > 0 and not tiene_taquete:
        errores.append(
            f"Falta el taquete correcto en el despiece para altura de cabecera "
            f"{'>= 4025mm (MPR0833)' if usa_taquete_grande else '< 4025mm (TEM-0019 o MPR0313)'}."
        )
    taquetes_totales = sum(
        m.get("pzas", 0) for m in materiales if "taquete" in (m.get("descripcion") or "").lower()
    )
    if n_cabeceras > 0 and taquetes_totales != n_cabeceras * 8:
        errores.append(f"Taquetes totales ({taquetes_totales}) debería ser 8 × n_cabeceras ({n_cabeceras * 8}).")

    calzas_totales = sum(
        m.get("pzas", 0) for m in materiales if "calza" in (m.get("descripcion") or "").lower()
    )
    if n_cabeceras > 0 and calzas_totales != n_cabeceras * 6:
        errores.append(f"Calzas totales ({calzas_totales}) debería ser 6 × n_cabeceras ({n_cabeceras * 6}).")

    # --- Tornillos de seguridad: 2 por larguero ---
    n_largueros = n_bays * n_corridas * n_niveles_usables * 2  # 2 largueros por par, por bay, por nivel, por corrida
    tornillos_totales = sum(
        m.get("pzas", 0) for m in materiales if m.get("codigo") == "MPR0272"
    )
    tornillos_esperados = n_largueros * 2
    if n_largueros > 0 and tornillos_totales != tornillos_esperados:
        errores.append(
            f"Tornillos de seguridad MPR0272 ({tornillos_totales}) debería ser "
            f"2 × n_largueros = {tornillos_esperados}."
        )

    # --- Tensores obligatorios en carga ligera ---
    if ligera:
        tensores_totales = sum(
            m.get("pzas", 0) for m in materiales if "tensor" in (m.get("descripcion") or "").lower()
        )
        pares_largueros_esperados = n_bays * n_corridas * n_niveles_usables
        if pares_largueros_esperados > 0 and tensores_totales < pares_largueros_esperados:
            errores.append(
                f"Faltan tensores unidores (obligatorios en carga ligera): hay {tensores_totales}, "
                f"se esperaban al menos {pares_largueros_esperados} (1 por par de largueros)."
            )

    # --- Familias no mezcladas ---
    prefijos_pesada = ("CRG-", "LRS-", "LRC-")
    prefijos_ligera = ("CRL-", "LRL-")
    tiene_pesada = any((m.get("codigo") or "").startswith(prefijos_pesada) for m in materiales)
    tiene_ligera = any((m.get("codigo") or "").startswith(prefijos_ligera) for m in materiales)
    if tiene_pesada and tiene_ligera:
        errores.append("El despiece mezcla piezas de familia PESADA y LIGERA (postes 73mm vs 38mm no son compatibles).")
    if pesada and tiene_ligera:
        errores.append("especificacion es PESADA pero el despiece incluye piezas de familia LIGERA.")
    if ligera and tiene_pesada:
        errores.append("especificacion es LIGERA pero el despiece incluye piezas de familia PESADA.")

    # --- Capacidad vs carga (memoria) ---
    carga_modulo = memoria.get("carga_modulo_kg")
    cap_marco = memoria.get("cap_marco_kg")
    if carga_modulo is not None:
        cap_max_familia = CAP_MARCO_PESADA_KG if pesada else (CAP_MARCO_LIGERA_KG if ligera else None)
        if cap_marco is not None and cap_max_familia is not None and cap_marco > cap_max_familia:
            errores.append(f"cap_marco_kg={cap_marco} excede el máximo de la familia ({cap_max_familia}kg).")
        cap_referencia = cap_marco or cap_max_familia
        if cap_referencia is not None and carga_modulo > cap_referencia / FACTOR_SEGURIDAD_MIN:
            errores.append(
                f"carga_modulo_kg={carga_modulo} excede el límite con factor de seguridad "
                f"{FACTOR_SEGURIDAD_MIN} (máximo permitido: {cap_referencia / FACTOR_SEGURIDAD_MIN:.0f}kg "
                f"sobre cap_marco_kg={cap_referencia})."
            )

    # --- Entrepaños: calibre válido ---
    for m in materiales:
        desc = (m.get("descripcion") or "").lower()
        if "entrepañ" in desc or "entrepan" in desc:
            cal_match = re.search(r"calibre\s*(\d+)", desc)
            if cal_match:
                calibre = int(cal_match.group(1))
                if pesada and calibre not in (14, 18, 22):
                    errores.append(f"Entrepaño '{m.get('codigo')}' calibre {calibre} inválido para PESADA (14/18/22).")
                if ligera and calibre not in (18, 22):
                    errores.append(f"Entrepaño '{m.get('codigo')}' calibre {calibre} inválido para LIGERA (18/22, no 14).")

    # --- Materiales sin precio (aviso, no bloqueante si viene del placeholder) ---
    sin_precio = [m.get("codigo") for m in materiales if m.get("precio") in (None, 0)]
    if sin_precio:
        errores.append(
            f"AVISO (no crítico): {len(sin_precio)} renglón(es) sin precio real: {sin_precio}. "
            "Verifica el catálogo antes de enviar la cotización al cliente."
        )

    return errores


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
