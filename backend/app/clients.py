"""
Clientes singleton (Supabase, Groq, Anthropic, OCR) — se crean una sola vez
al importar este módulo y se comparten en toda la app.
"""
import os
from supabase import create_client, Client
from groq import Groq
from anthropic import Anthropic
import easyocr

from . import config  # noqa: F401  (garantiza que el .env ya esté cargado)

supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
supabase_service: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
ocr_reader = easyocr.Reader(['es'])
