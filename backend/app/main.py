"""
Punto de ensamblaje de la aplicación FastAPI: crea la instancia `app`,
registra middleware CORS y todos los routers, y conecta el lifespan del bot
de Telegram. La lógica de negocio vive en services/, no aquí.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .core.logger import configurar_logging

configurar_logging()

from .config import CORS_ORIGINS
from .core.error_logger import inferir_componente, registrar_error
from .cors import _LocalhostCORSMiddleware
from .telegram.bot import lifespan

from .routers import storage, catalogo, disenos, sistema, correcciones, rag, stats

log = logging.getLogger("main")

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


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Persiste solo los 5xx -- un 404 o un 400 no es un fallo del sistema,
    es un cliente pidiendo algo que no existe o mal formado."""
    if exc.status_code >= 500:
        registrar_error(inferir_componente(request.url.path), str(exc.detail), endpoint=request.url.path)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Excepcion no manejada en %s", request.url.path)
    registrar_error(inferir_componente(request.url.path), str(exc), endpoint=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Error interno del servidor."})


app.include_router(sistema.router)
app.include_router(storage.router)
app.include_router(catalogo.router)
app.include_router(disenos.router)
app.include_router(correcciones.router)
app.include_router(rag.router)
app.include_router(stats.router)
