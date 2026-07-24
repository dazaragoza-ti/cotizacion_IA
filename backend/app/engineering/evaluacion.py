"""
Evaluación automática — corre los proyectos de referencia reales
(app/ai/knowledge/ejemplos/*.json) contra el validador estructural y el
Compatibility Engine.

No llama a Claude — es intencional. Su objetivo es una red de seguridad
BARATA y RÁPIDA: cada vez que edites `prompts/system.md`, agregues un
código al catálogo, o toques `validator_engine.py`/`compatibility.py`,
corre esto para confirmar que los ejemplos "dorados" siguen siendo válidos
según las reglas actuales, antes de desplegar.

Uso:
    python -m app.engineering.evaluacion

O desde código:
    from app.engineering.evaluacion import evaluar_ejemplos
    resultado = evaluar_ejemplos()
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from . import validator_engine
from .compatibility import verificar_compatibilidad_proyecto
from ..services.catalogo_pm_service import consultar_catalogo_pm

EJEMPLOS_DIR = Path(__file__).parent.parent / "ai" / "knowledge" / "ejemplos"


@dataclass
class ResultadoEjemplo:
    archivo: str
    valido: bool
    errores_validador: list[str] = field(default_factory=list)
    advertencias_validador: list[str] = field(default_factory=list)
    errores_compatibilidad: list[str] = field(default_factory=list)


@dataclass
class ResultadoEvaluacion:
    resultados: list[ResultadoEjemplo] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.resultados)

    @property
    def validos(self) -> int:
        return sum(1 for r in self.resultados if r.valido)

    def resumen(self) -> str:
        return f"{self.validos}/{self.total} ejemplos válidos"

    def como_texto(self) -> str:
        lineas = [f"# Evaluación de ejemplos — {self.resumen()}\n"]
        for r in self.resultados:
            estado = "✅" if r.valido else "❌"
            lineas.append(f"\n## {estado} {r.archivo}")
            for e in r.errores_validador:
                lineas.append(f"  - [validador] {e}")
            for e in r.errores_compatibilidad:
                lineas.append(f"  - [compatibility] {e}")
            for a in r.advertencias_validador:
                lineas.append(f"  - [aviso] {a}")
        return "\n".join(lineas)


def evaluar_ejemplos() -> ResultadoEvaluacion:
    """
    Carga cada .json de knowledge/ejemplos/ (ignora README.md y cualquier
    .html) y lo corre contra validator_engine + compatibility. Un ejemplo
    "dorado" debe salir SIEMPRE limpio — si no, o el ejemplo quedó
    desactualizado, o algo que se tocó en las reglas lo rompió.
    """
    catalogo_pm = consultar_catalogo_pm()
    evaluacion = ResultadoEvaluacion()

    if not EJEMPLOS_DIR.exists():
        return evaluacion

    for archivo in sorted(EJEMPLOS_DIR.glob("*.json")):
        try:
            proyecto = json.loads(archivo.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            evaluacion.resultados.append(ResultadoEjemplo(
                archivo=archivo.name, valido=False,
                errores_validador=[f"No se pudo leer/parsear el JSON: {e}"],
            ))
            continue

        validacion = validator_engine.validar(proyecto, catalogo=catalogo_pm)
        errores_compat = verificar_compatibilidad_proyecto(proyecto, catalogo_pm)

        evaluacion.resultados.append(ResultadoEjemplo(
            archivo=archivo.name,
            valido=(not validacion.errores) and (not errores_compat),
            errores_validador=list(validacion.errores),
            advertencias_validador=list(validacion.advertencias),
            errores_compatibilidad=errores_compat,
        ))

    return evaluacion


if __name__ == "__main__":
    resultado = evaluar_ejemplos()
    print(resultado.como_texto())
    raise SystemExit(0 if resultado.validos == resultado.total else 1)
