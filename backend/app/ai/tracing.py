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


def anotar_run(*, usage_metadata: dict | None = None, **metadata) -> None:
    """
    Adjunta información al run @traceable activo (Sprint 2, Fase 5):

    - `usage_metadata={"input_tokens": ..., "output_tokens": ..., "total_tokens": ...}`
      para que LangSmith calcule el COSTO real de la llamada (antes solo se veían
      tokens sueltos, sin costo).
    - cualquier otro kwarg (p. ej. `system_prompt=...`) se agrega como metadata
      extra visible en la traza.

    No-op si LangSmith no está instalado/activo o si se llama fuera de una
    función @traceable (nunca debe romper el flujo real — es puramente
    observabilidad).
    """
    if not _LANGSMITH_DISPONIBLE:
        return
    try:
        from langsmith.run_helpers import get_current_run_tree
        run_tree = get_current_run_tree()
        if run_tree is None:
            return
        if usage_metadata is not None:
            run_tree.set(usage_metadata=usage_metadata)
        if metadata:
            run_tree.set(metadata=metadata)
    except Exception:  # noqa: BLE001 — tracing nunca debe tumbar el flujo real
        pass
