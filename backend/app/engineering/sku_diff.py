"""
SkuDiffExtractor — Fase 0c del Sprint 2 (aprendizaje continuo).

Hoy una corrección guarda el JSON COMPLETO del proyecto antes/después
(`correcciones_armado.proyecto_json_antes` / `proyecto_json_despues`), no el
cambio a nivel de SKU. Este módulo extrae ese cambio: qué pieza se quitó, cuál
se agregó y —lo más valioso— qué SKU REEMPLAZÓ a cuál. De ahí cuelgan las
relaciones `reemplaza_por` del grafo (Fase 3) y la promoción a regla (Fase 4);
sin este extractor esas partes del sprint son imposibles.

Contrato del JSON de proyecto (verificado contra `validator_engine.py`):
- `proyecto["materiales"]`: list[dict]
- cada material: {"codigo": <sku: str>, "pzas": <cantidad: int>, ...}
Los códigos pueden traer sufijo de color (-AZ, -NA, ...); se normalizan igual
que `validator_engine._codigo_base` (ver `normalizar_sku`).
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

# Sufijos de color — mirror de validator_engine._codigo_base (validator_engine.py:151).
# TODO(sprint2): unificar ambos en un único normalizador compartido para evitar drift.
_SUFIJO_COLOR = re.compile(r"-(AZ|NA|AC|GA|AM|VR|GR|BL|RJ)$", re.IGNORECASE)
_PREFIJO_FAMILIA = re.compile(r"^[A-Za-z]+")


def normalizar_sku(codigo: str | None) -> str:
    """Normaliza un código: mayúsculas, sin espacios, sin sufijo de color."""
    if not codigo:
        return ""
    return _SUFIJO_COLOR.sub("", codigo.strip().upper())


def _familia(sku: str) -> str:
    """Prefijo alfabético del SKU, usado para emparejar reemplazos.

    'LRS7355' y 'LRS7410' comparten familia 'LRS' → candidatos a reemplazo.
    """
    m = _PREFIJO_FAMILIA.match(sku)
    return m.group(0) if m else sku


def extraer_piezas(proyecto: dict | None) -> dict[str, int]:
    """`{sku_normalizado: cantidad_total}` a partir de `proyecto['materiales']`.

    Suma cantidades si un mismo código aparece en varias filas del despiece.
    """
    piezas: dict[str, int] = {}
    if not proyecto:
        return piezas
    for m in (proyecto.get("materiales") or []):
        if not isinstance(m, dict):
            continue
        sku = normalizar_sku(m.get("codigo"))
        if not sku:
            continue
        try:
            pzas = int(m.get("pzas") or 0)
        except (TypeError, ValueError):
            pzas = 0
        piezas[sku] = piezas.get(sku, 0) + pzas
    return piezas


@dataclass
class DiffSku:
    """Resultado de comparar el despiece de dos versiones de un proyecto."""

    reemplazos: list[tuple[str, str]] = field(default_factory=list)  # (viejo, nuevo)
    agregados: list[str] = field(default_factory=list)
    eliminados: list[str] = field(default_factory=list)
    # (sku, pzas_antes, pzas_despues) para el mismo SKU que cambió de cantidad
    cambios_cantidad: list[tuple[str, int, int]] = field(default_factory=list)

    @property
    def hubo_cambio_de_piezas(self) -> bool:
        return bool(self.reemplazos or self.agregados or self.eliminados)

    def resumen(self) -> str:
        partes = []
        for viejo, nuevo in self.reemplazos:
            partes.append(f"{viejo} → {nuevo}")
        if self.agregados:
            partes.append("agregados: " + ", ".join(self.agregados))
        if self.eliminados:
            partes.append("eliminados: " + ", ".join(self.eliminados))
        return "; ".join(partes) or "sin cambios de piezas"


def diff_skus(antes: dict | None, despues: dict | None) -> DiffSku:
    """
    Compara los materiales de dos versiones de un proyecto y clasifica el cambio.

    Heurística de reemplazo (v1, conservadora):
      - Un SKU que desaparece + un SKU que aparece, ambos de la MISMA familia
        (mismo prefijo alfabético), se interpretan como reemplazo viejo→nuevo.
      - Con varias altas/bajas de la misma familia se emparejan en orden (1↔1).
      - Lo que no se puede emparejar 1↔1 queda como `agregados`/`eliminados`
        sueltos: la promoción a regla (Fase 4) exige señal limpia, así que los
        casos ambiguos N↔M no generan relación `reemplaza_por` en v1.
    """
    p_antes = extraer_piezas(antes)
    p_despues = extraer_piezas(despues)

    eliminados = [s for s in p_antes if s not in p_despues]
    agregados = [s for s in p_despues if s not in p_antes]

    cambios_cantidad = [
        (s, p_antes[s], p_despues[s])
        for s in p_antes
        if s in p_despues and p_antes[s] != p_despues[s]
    ]

    # Emparejar bajas y altas por familia para detectar reemplazos.
    elim_por_fam: dict[str, list[str]] = defaultdict(list)
    for s in eliminados:
        elim_por_fam[_familia(s)].append(s)
    agr_por_fam: dict[str, list[str]] = defaultdict(list)
    for s in agregados:
        agr_por_fam[_familia(s)].append(s)

    reemplazos: list[tuple[str, str]] = []
    elim_restantes: list[str] = []
    agr_emparejados: set[str] = set()
    for fam, viejos in elim_por_fam.items():
        nuevos = agr_por_fam.get(fam, [])
        for i, viejo in enumerate(viejos):
            if i < len(nuevos):
                nuevo = nuevos[i]
                reemplazos.append((viejo, nuevo))
                agr_emparejados.add(nuevo)
            else:
                elim_restantes.append(viejo)

    agr_restantes = [s for s in agregados if s not in agr_emparejados]

    return DiffSku(
        reemplazos=reemplazos,
        agregados=agr_restantes,
        eliminados=elim_restantes,
        cambios_cantidad=cambios_cantidad,
    )
