"""
Tracing con LangSmith — observabilidad de cada llamada a Claude (prompt
completo, respuesta, tokens, tiempo, costo), visible en smith.langchain.com.

No usamos LangChain ni LangGraph para nada más del proyecto — LangSmith se
puede usar solo, con el decorador `@traceable` alrededor de cualquier
función, sin acoplar el resto del código a esos frameworks.

Diseñado para fallar suave: si `langsmith` no está instalado, o no hay
LANGSMITH_API_KEY en el .env, el decorador se vuelve un no-op — el bot
sigue funcionando exactamente igual, solo sin trazas.
"""
from __future__ import annotations

import functools
import inspect
import os

try:
    from langsmith import traceable as _traceable_real
    _LANGSMITH_DISPONIBLE = True
except ImportError:
    _LANGSMITH_DISPONIBLE = False


def _envolver_sin_tracing(func):
    """
    Envuelve `func` descartando `langsmith_extra` (el kwarg especial que
    @traceable normalmente intercepta) — así los call sites pueden pasar
    `langsmith_extra=...` sin importar si LangSmith está instalado o no.
    """
    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def wrapper_async(*args, **kwargs):
            kwargs.pop("langsmith_extra", None)
            return await func(*args, **kwargs)
        return wrapper_async

    @functools.wraps(func)
    def wrapper_sync(*args, **kwargs):
        kwargs.pop("langsmith_extra", None)
        return func(*args, **kwargs)
    return wrapper_sync


def _traceable_noop(*dargs, **dkwargs):
    """Decorador de reemplazo: no traza nada, pero sigue aceptando (y descartando) langsmith_extra."""
    if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
        return _envolver_sin_tracing(dargs[0])

    def decorador(func):
        return _envolver_sin_tracing(func)
    return decorador


def tracing_activo() -> bool:
    """True solo si el paquete está instalado Y hay API key configurada."""
    return _LANGSMITH_DISPONIBLE and bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))


# Este es el decorador que se usa en el resto del proyecto: `from app.ai.tracing import traceable`.
traceable = _traceable_real if _LANGSMITH_DISPONIBLE else _traceable_noop
