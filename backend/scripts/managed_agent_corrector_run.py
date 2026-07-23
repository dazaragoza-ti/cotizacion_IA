"""RUNTIME — lanza una sesión del agente corrector 3D bajo demanda.

Requiere que ya hayas corrido managed_agent_corrector_setup.py y guardado
MANAGED_AGENT_CORRECTOR_ID / MANAGED_AGENT_ENVIRONMENT_ID (en backend/.env
o como variables de entorno).

El token de GitHub se toma de `gh auth token` (ya autenticado localmente
como dazaragoza-ti, scope 'repo') -- no se pide ni se guarda por separado.
Nunca entra al sandbox del agente en texto plano: el mount de
github_repository lo inyecta un proxy de Anthropic al hacer git pull/push,
y abrir_pull_request lo usa aquí mismo, en tu máquina, vía `gh pr create`.

Uso:
    cd backend
    ./venv/Scripts/python.exe scripts/managed_agent_corrector_run.py "<instrucción para el agente>"
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")  # la consola de Windows manda cp1252 y el stream del agente usa Unicode (p.ej. "→")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # asegura que "backend/" (no solo "backend/scripts/") esté en sys.path

import anthropic

from app import config as _app_config  # noqa: F401 -- carga backend/.env

REPO_URL = "https://github.com/dazaragoza-ti/cotizacion_IA"
BASE_BRANCH = "josue"
WORKSPACE = "default"  # cambia por el ID de tu workspace si tu API key no está en el Default


def _github_token() -> str:
    token = os.getenv("GITHUB_TOKEN")
    if token:
        return token
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            "No se pudo obtener un token de GitHub (ni GITHUB_TOKEN ni `gh auth token`). "
            "Corre `gh auth login` o exporta GITHUB_TOKEN."
        ) from e


def _abrir_pull_request(branch: str, titulo: str, descripcion: str) -> str:
    """Ejecuta EN EL HOST (nunca en el sandbox del agente) -- tiene el token de gh."""
    try:
        out = subprocess.run(
            [
                "gh", "pr", "create",
                "--repo", "dazaragoza-ti/cotizacion_IA",
                "--base", BASE_BRANCH,
                "--head", branch,
                "--title", titulo,
                "--body", descripcion,
            ],
            capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"ERROR al abrir el PR: {e.stderr.strip()}"


def main() -> None:
    instruccion = " ".join(sys.argv[1:]) or (
        "Revisa los ejemplos dorados en backend/app/ai/knowledge/ejemplos/*.json. "
        "Corre validador_geometria.py (validar_modulo y validar_corrida) sobre cada "
        "uno y regenera sus renders. Si encuentras un defecto correctable, arréglalo "
        "en modelo_3d.py, confirma con el validador y los renders, y abre un PR."
    )

    agent_id = os.environ["MANAGED_AGENT_CORRECTOR_ID"]
    environment_id = os.environ["MANAGED_AGENT_ENVIRONMENT_ID"]
    github_token = _github_token()

    client = anthropic.Anthropic()

    session = client.beta.sessions.create(
        agent=agent_id,  # latest version
        environment_id=environment_id,
        title="Corrector 3D -- sesión manual",
        resources=[
            {
                "type": "github_repository",
                "url": REPO_URL,
                "authorization_token": github_token,
                "mount_path": "/workspace/repo",
                "checkout": {"type": "branch", "name": BASE_BRANCH},
            }
        ],
    )
    print(f"Sesión: {session.id}")
    print(f"Trace en vivo: https://platform.claude.com/workspaces/{WORKSPACE}/sessions/{session.id}")
    print()

    # Stream-first: abre el stream ANTES de mandar el mensaje inicial.
    with client.beta.sessions.events.stream(session_id=session.id) as stream:
        client.beta.sessions.events.send(
            session_id=session.id,
            events=[{"type": "user.message", "content": [{"type": "text", "text": instruccion}]}],
        )

        for event in stream:
            if event.type == "agent.message":
                for block in event.content:
                    if block.type == "text":
                        print(block.text, end="", flush=True)

            elif event.type == "agent.tool_use":
                print(f"\n[tool: {event.name}] {event.input}")

            elif event.type == "agent.custom_tool_use":
                if event.name == "abrir_pull_request":
                    resultado = _abrir_pull_request(**event.input)
                    print(f"\n[abrir_pull_request] {resultado}")
                    client.beta.sessions.events.send(
                        session_id=session.id,
                        events=[{
                            "type": "user.custom_tool_result",
                            "custom_tool_use_id": event.id,
                            "content": [{"type": "text", "text": resultado}],
                        }],
                    )
                else:
                    print(f"\n[custom tool desconocida: {event.name}]")

            elif event.type == "session.error":
                print(f"\n[ERROR] {event}")

            elif event.type == "session.status_terminated":
                print("\n--- sesión terminada ---")
                break

            elif event.type == "session.status_idle":
                if event.stop_reason.type != "requires_action":
                    print("\n--- agente en idle, terminado ---")
                    break

    print(f"\nRevisa el trace completo o descarga artefactos con:\n  files.list(scope_id='{session.id}')")


if __name__ == "__main__":
    main()
