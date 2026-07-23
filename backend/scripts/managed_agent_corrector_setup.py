"""SETUP — corre esto UNA SOLA VEZ (o cuando quieras cambiar el modelo,
system prompt o tools del agente corrector). Crea el Environment y
actualiza el Managed Agent existente (agent_01P1Ejo6DAcEFS2NeksamS83) con
la versión "ambiciosa": bash + archivos + validador geométrico + visión +
tool para abrir PRs.

No lo llames desde el pipeline de producción -- guarda los IDs que imprime
al final (AGENT_ID ya lo conoces, ENVIRONMENT_ID es nuevo) en
backend/.env o donde prefieras, y úsalos en
managed_agent_corrector_run.py.

Uso:
    cd backend
    ./venv/Scripts/python.exe scripts/managed_agent_corrector_setup.py
"""
from __future__ import annotations

from pathlib import Path

import anthropic

from app import config as _app_config  # noqa: F401 -- carga backend/.env

AGENT_ID = "agent_01P1Ejo6DAcEFS2NeksamS83"  # el agente ya existente en consola, se actualiza (nunca se crea uno nuevo)
ENVIRONMENT_NAME = "plataforma-racks-corrector-3d"

BASE = Path(__file__).parent.parent  # backend/
SYSTEM_PROMPT = (BASE / "app" / "ai" / "prompts" / "corrector_3d.md").read_text(encoding="utf-8")

TOOLS = [
    {"type": "agent_toolset_20260401"},  # bash, read, write, edit, glob, grep, web_fetch, web_search
    {
        "type": "custom",
        "name": "abrir_pull_request",
        "description": (
            "Abre un Pull Request en GitHub desde una rama que ya pusheaste "
            "hacia 'josue'. Úsala SOLO después de: (1) confirmar con "
            "validador_geometria.py que el defecto desapareció, (2) "
            "regenerar los renders y compararlos contra la referencia, y "
            "(3) hacer commit + push de tu rama fix/<algo> con bash."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "branch": {"type": "string", "description": "Nombre de la rama ya pusheada, ej. fix/travesano-vs-larguero"},
                "titulo": {"type": "string", "description": "Título breve del PR"},
                "descripcion": {
                    "type": "string",
                    "description": "Qué defecto encontraste, cómo lo confirmaste (validador/render) y qué cambiaste",
                },
            },
            "required": ["branch", "titulo", "descripcion"],
        },
    },
]


def main() -> None:
    client = anthropic.Anthropic()

    # 1) Environment -- reusa si ya existe (nombre único), si no lo crea.
    environment_id = None
    for env in client.beta.environments.list():
        if env.name == ENVIRONMENT_NAME:
            environment_id = env.id
            print(f"Environment ya existe: {environment_id}")
            break
    if environment_id is None:
        environment = client.beta.environments.create(
            name=ENVIRONMENT_NAME,
            config={
                "type": "cloud",
                # unrestricted: necesita pip install trimesh/dracopy/numpy/matplotlib
                # (no vienen preinstalados) y salida normal de git.
                "networking": {"type": "unrestricted"},
            },
        )
        environment_id = environment.id
        print(f"Environment creado: {environment_id}")

    # 2) Agent -- ACTUALIZA el existente (nueva versión), nunca crea uno nuevo.
    actual = client.beta.agents.retrieve(AGENT_ID)
    print(f"Agente actual: {actual.id}, version {actual.version} ({actual.name!r})")
    agent = client.beta.agents.update(
        AGENT_ID,
        version=actual.version,
        name="Corrector 3D — Racks PM",
        description=(
            "Corrige defectos de ensamble en modelo_3d.py: corre el "
            "validador geométrico + regenera renders + compara contra "
            "referencia, edita el generador cuando encuentra un defecto "
            "correctable, y abre un PR contra josue."
        ),
        model="claude-opus-4-8",
        system=SYSTEM_PROMPT,
        tools=TOOLS,
    )
    print(f"Agente actualizado: {agent.id} -> version {agent.version}")

    print()
    print("Guarda estos valores (ej. en backend/.env):")
    print(f"  MANAGED_AGENT_CORRECTOR_ID={agent.id}")
    print(f"  MANAGED_AGENT_CORRECTOR_VERSION={agent.version}")
    print(f"  MANAGED_AGENT_ENVIRONMENT_ID={environment_id}")


if __name__ == "__main__":
    main()
