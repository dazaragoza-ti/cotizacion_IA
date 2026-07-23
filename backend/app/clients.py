"""
Clientes singleton (Supabase, Groq, Anthropic, OCR) — se crean una sola vez
al importar este módulo y se comparten en toda la app.
"""
import os
from supabase import create_client, Client
from groq import Groq
from anthropic import Anthropic

from . import config  # noqa: F401  (garantiza que el .env ya esté cargado)

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
supabase_service: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

_ocr_reader = None


def __getattr__(name):
    """ocr_reader es perezoso: easyocr carga un modelo pesado (CPU, sin GPU
    en este servidor) que la mayoría de módulos que importan de aquí
    (groq_client, supabase, anthropic_client) no necesitan para nada. Se
    instancia solo la primera vez que alguien realmente lo usa
    (ocr_service.extraer_texto_imagen), no al importar este módulo."""
    if name == "ocr_reader":
        global _ocr_reader
        if _ocr_reader is None:
            import easyocr
            _ocr_reader = easyocr.Reader(["es"])
        return _ocr_reader
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
