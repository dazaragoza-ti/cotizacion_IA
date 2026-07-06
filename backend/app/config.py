"""
Configuración y constantes globales del backend.
Carga el .env una sola vez; el resto de módulos importan desde aquí.
"""
import os
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path=dotenv_path)

# Carpeta backend/ real (dos niveles arriba de este archivo: app/config.py -> backend/).
# Ahí vive node_modules/ (gltf-transform), NO junto a los routers/servicios.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# URL de tu visualizador alojado en GitHub Pages
URL_FRONTEND = "https://dazaragoza-ti.github.io/cotizacion_IA/index.html"

# Orígenes CORS permitidos explícitamente (producción).
CORS_ORIGINS = [
    "https://dazaragoza-ti.github.io",  # Producción en GitHub Pages
]
