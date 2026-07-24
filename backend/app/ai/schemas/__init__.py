"""Contratos tipados de salida de los agentes (proyectista, QA visual, etc.)."""

from .proyecto_pm import (
    ProyectoPM,
    errores_contrato_proyecto,
    validar_proyecto_pm,
)

__all__ = [
    "ProyectoPM",
    "errores_contrato_proyecto",
    "validar_proyecto_pm",
]
