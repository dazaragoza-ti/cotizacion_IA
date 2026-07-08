"""
Punto de ensamblaje de la aplicación FastAPI: crea la instancia `app`,
registra middleware CORS y todos los routers, y conecta el lifespan del bot
de Telegram. La lógica de negocio vive en services/, no aquí.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import CORS_ORIGINS
from .cors import _LocalhostCORSMiddleware
from .telegram.bot import lifespan

from .routers import storage, catalogo, disenos, sistema, correcciones, rag

app = FastAPI(
    title="RackBuilder 3D API",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Para desarrollo local: permite cualquier origen http://localhost:* (Flutter
# web asigna un puerto aleatorio cada vez que corre).
app.add_middleware(_LocalhostCORSMiddleware)

app.include_router(sistema.router)
app.include_router(storage.router)
app.include_router(catalogo.router)
app.include_router(disenos.router)
app.include_router(correcciones.router)
app.include_router(rag.router)
