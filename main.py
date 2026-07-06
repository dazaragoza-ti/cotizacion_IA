"""
Punto de entrada para uvicorn (`uvicorn main:app --reload`).

Toda la lógica real vive ahora en app/ (arquitectura por capas: clients,
config, services/, routers/, telegram/). Este archivo solo re-exporta la
instancia de FastAPI para no romper el comando de arranque que ya tenías
configurado en tu servidor/Procfile/systemd.
"""
from app.main import app

__all__ = ["app"]
