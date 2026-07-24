"""
Contrato tipado del JSON de proyecto del proyectista PM.

Alineado con el bloque ```json de `prompts/system.md` y con lo que consumen
el validador, el pipeline de planos/XLSX y el adaptador del visor 3D.
Validación post-parse (Pydantic) — mismo espíritu que el `OUTPUT_SCHEMA` de
`qa_visual_client.py`, pero del lado del orquestador porque Claude no emite
JSON Schema nativo en este flujo.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class LayoutPM(BaseModel):
    """Rejilla simple — sin `zones` ni claves inventadas."""

    model_config = ConfigDict(extra="ignore")

    tipo: str
    modulos_x: int = Field(ge=1)
    modulos_y: int = Field(ge=1)
    frente_mm: int | float = Field(gt=0)
    fondo_mm: int | float = Field(gt=0)
    pasillo_mm: int | float | None = None
    niveles: list[int | float]
    altura_total_mm: int | float | None = None
    peralte_larguero_mm: int | float | None = None

    @field_validator("niveles")
    @classmethod
    def _niveles_empiezan_en_cero(cls, v: list[int | float]) -> list[int | float]:
        if not v:
            raise ValueError("layout.niveles no puede estar vacío")
        if float(v[0]) != 0.0:
            raise ValueError("layout.niveles debe empezar en 0")
        return v


class MaterialPM(BaseModel):
    model_config = ConfigDict(extra="ignore")

    pzas: int | float = Field(gt=0)
    codigo: str = Field(min_length=1)
    descripcion: str | None = None
    color: str | None = None
    obs: str | None = None
    precio: int | float | None = None


class MemoriaPM(BaseModel):
    model_config = ConfigDict(extra="allow")

    tipo_carga: str | None = None
    tarima_lxa: str | None = None
    peso_tarima_kg: int | float | None = None
    tarimas_nivel: int | float | None = None
    carga_nivel_kg: int | float | None = None
    carga_modulo_kg: int | float | None = None
    cap_marco_kg: int | float | None = None
    factor_seguridad: int | float | None = None
    anclaje: str | None = None
    montacargas: str | None = None


class ProyectoPM(BaseModel):
    """Contrato del JSON que emite el proyectista en un bloque ```json."""

    model_config = ConfigDict(extra="ignore")

    proyecto: str | None = None
    clave: str = Field(min_length=1)
    cliente: str | None = None
    elaboro: str | None = None
    reviso: str | None = None
    aprobo: str | None = None
    fecha: str | None = None
    revision: str | None = None
    material: str | None = None
    especificacion: str | None = None
    calibre: str | None = None
    dim_corte: str | None = None
    layout: LayoutPM
    materiales: list[MaterialPM] = Field(min_length=1)
    memoria: MemoriaPM | dict[str, Any] | None = None
    observaciones: list[str] | str | None = None
    render_path: str | None = None


def validar_proyecto_pm(data: dict[str, Any]) -> ProyectoPM:
    """Parsea/valida el dict crudo. Lanza ValidationError si no cumple."""
    return ProyectoPM.model_validate(data)


def errores_contrato_proyecto(data: dict[str, Any] | None) -> list[str]:
    """Lista de mensajes legibles para reinyectar a Claude (mismo estilo
    que los errores del Validator Engine). Vacía si el contrato se cumple
    o si `data` es None (sin JSON no hay contrato que validar aquí)."""
    if data is None:
        return []
    try:
        validar_proyecto_pm(data)
        return []
    except ValidationError as exc:
        mensajes: list[str] = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err.get("loc") or ())
            msg = err.get("msg") or "inválido"
            mensajes.append(f"Contrato JSON: {loc}: {msg}" if loc else f"Contrato JSON: {msg}")
        return mensajes
