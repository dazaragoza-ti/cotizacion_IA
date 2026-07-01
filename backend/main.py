import os
import fitz  # PyMuPDF
import easyocr
import json
import asyncio
import urllib.parse  # Para codificar de forma segura las credenciales en la URL
import urllib.request
import urllib.error
import subprocess
import tempfile
import shutil
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client, Client
from pydantic import BaseModel
from groq import Groq
from anthropic import Anthropic  
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# Importaciones para el Bot de Telegram
from telegram import Update
from telegram.request import HTTPXRequest
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Cargar variables de entorno
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=dotenv_path)

# --- 1. INICIALIZACIÓN DE CLIENTES Y SERVICIOS ---
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
supabase_service: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")
)
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
ocr_reader = easyocr.Reader(['es'])
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# URL de tu visualizador alojado en GitHub Pages
URL_FRONTEND = "https://dazaragoza-ti.github.io/cotizacion_IA/index.html"


# --- 2. DEFINICIÓN DEL LIFESPAN (CICLO DE VIDA) Y APP DE FASTAPI ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    t_request = HTTPXRequest(connect_timeout=15.0, read_timeout=15.0)

    tg_app = Application.builder().token(BOT_TOKEN).request(t_request).build()
    tg_app.add_handler(CommandHandler("start", start_command))

    filtro_total = filters.Document.ALL | filters.PHOTO | filters.TEXT | filters.VOICE
    tg_app.add_handler(MessageHandler(filtro_total, manejar_mensaje_telegram))

    await tg_app.initialize()
    await tg_app.start()

    await tg_app.updater.start_polling(timeout=10, drop_pending_updates=True)
    print("🤖 Servidor de Ingeniería CAD e Inteligencia de Ensambles en ejecución...")
    yield

    try:
        if tg_app.updater and tg_app.updater.running:
            await tg_app.updater.stop()
    except Exception as e:
        print(f"⚠️ Nota: Excepción capturada durante el apagado del updater: {e}")

    try:
        await tg_app.stop()
        await tg_app.shutdown()
        print("🔌 Conexiones de Telegram cerradas con éxito.")
    except Exception as e:
        print(f"⚠️ Nota: Excepción capturada durante el apagado de la aplicación de Telegram: {e}")


# Instancia principal de FastAPI
app = FastAPI(lifespan=lifespan)

# ORÍGENES PERMITIDOS EXPLÍCITOS (Soluciona el bloqueo de CORS al usar allow_credentials=True)
origins = [
    "http://localhost:4200",         # Entorno local de desarrollo de Angular
    "http://localhost:8000",         # Swagger / FastAPI local docs
    "https://dazaragoza-ti.github.io" # Producción en GitHub Pages
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- 3. FUNCIONES AUXILIARES Y GESTIÓN DE CATÁLOGO ---
def consultar_catalogo_piezas() -> list:
    """
    Trae el inventario de componentes reales disponibles de Supabase.
    Si la tabla está vacía, no existe, o la consulta falla, provee el catálogo técnico
    con los tres modelos de precisión reales que ya tienes integrados en Supabase.
    """
    fallback_piezas = [
        {"sku": "(-)_RACK_180X61X151", "nombre": "Rack Estructural Base 1.80m x 0.61m", "tipo": "rack_base", "longitud_metros": 1.80, "altura_metros": 1.51, "profundidad_metros": 0.61},
        {"sku": "CABECERA_302X91_CON_TRAVESANO", "nombre": "Cabecera Lateral 3.02m con Travesaño", "tipo": "marco", "longitud_metros": 0.08, "altura_metros": 3.02, "profundidad_metros": 0.91},
        {"sku": "MENSULA_GOTA_CARGA_LIGERA_DERECHA", "nombre": "Ménsula Gota Carga Ligera Derecha", "tipo": "mensula"}
    ]
    try:
        resultado = supabase.table("catalogo_piezas").select("*").execute()
        if resultado.data and len(resultado.data) > 0:
            return resultado.data
        return fallback_piezas
    except Exception:
        return fallback_piezas


def obtener_ultimo_diseno(session_id: str) -> dict | None:
    """
    Recupera la versión más reciente del diseño actual para esta sesión de chat.
    """
    try:
        resultado = supabase.table("disenos_racks").select("*").eq("session_id", session_id).order("version_actual", desc=True).limit(1).execute()
        return resultado.data[0] if resultado.data else None
    except Exception:
        return None


def procesar_diseno_auto_correctivo(comentario_usuario: str, session_id: str, vendedor_id: str) -> dict:
    """
    Lógica del Agente de Ensamble:
    Calcula el ensamble de componentes en base a las piezas reales disponibles.
    """
    catalogo_disponible = consultar_catalogo_piezas()
    diseno_previo = obtener_ultimo_diseno(session_id)

    herramienta_guardar_diseno = {
        "name": "guardar_diseno_3d",
        "description": "Registra la matriz y geometría de ensamble 3D del rack.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo_rack": {"type": "string"},
                "peso_maximo_por_nivel_kg": {"type": "number"},
                "numero_niveles": {"type": "integer"},
                "marcos": {
                    "type": "array", 
                    "items": {
                        "type": "object", 
                        "properties": {
                            "sku": {"type": "string"}, 
                            "posicion": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}}
                        }
                    }
                },
                "vigas": {
                    "type": "array", 
                    "items": {
                        "type": "object", 
                        "properties": {
                            "sku": {"type": "string"}, 
                            "nivel": {"type": "integer"}, 
                            "posicion": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}}
                        }
                    }
                },
                "mensulas": {
                    "type": "array", 
                    "items": {
                        "type": "object", 
                        "properties": {
                            "sku": {"type": "string"}, 
                            "nivel": {"type": "integer"}, 
                            "lado": {"type": "string"}, 
                            "posicion": {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"}, "z": {"type": "number"}}}
                        }
                    }
                },
                "comentarios_adicionales": {"type": "string"}
            },
            "required": ["tipo_rack", "peso_maximo_por_nivel_kg", "numero_niveles", "marcos", "vigas", "mensulas", "comentarios_adicionales"]
        }
    }

    system_prompt = (
        "Eres un Ingeniero CAD Senior especializado en modelado espacial de racks industriales en 3D.\n"
        "Tu única tarea es calcular la colocación de componentes físicos en metros (ejes X, Y, Z).\n\n"
        "MODELOS REALES DISPONIBLES EN SUPABASE:\n"
        "1. '(-)_RACK_180X61X151': Módulo completo pre-ensamblado de 1 nivel (1.80m de largo, 1.51m de alto, 0.61m de profundidad).\n"
        "2. 'CABECERA_302X91_CON_TRAVESANO': Marco estructural lateral de 3.02m de altura, 0.91m de profundidad.\n"
        "3. 'MENSULA_GOTA_CARGA_LIGERA_DERECHA': Ménsula de acople drop-lock de carga ligera.\n\n"
        "INSTRUCCIONES DE DISEÑO INDUSTRIAL:\n"
        "- Si el usuario solicita un rack estándar de un solo nivel, utiliza directamente el modelo pre-armado '(-)_RACK_180X61X151' colocado en X=0, Y=0, Z=0.\n"
        "- Si el usuario solicita una estructura modular extendida o de múltiples niveles (ej: de 2 o 3 niveles de altura):\n"
        "  • Utiliza dos cabeceras 'CABECERA_302X91_CON_TRAVESANO' como soportes laterales colocados a los lados (ej: X = -0.9 y X = 0.9).\n"
        "  • Coloca las vigas horizontales a lo largo de las alturas Y requeridas (ej: nivel 1 en Y=0.8, nivel 2 en Y=1.8, nivel 3 en Y=2.7).\n"
        "  • En los extremos de cada viga de carga, coloca las ménsulas 'MENSULA_GOTA_CARGA_LIGERA_DERECHA' (posicionadas a la misma altura Y de la viga, en X = -0.9 y X = 0.9) para simular el enganche real de fabricación.\n\n"
        f"INVENTARIO TÉCNICO COMPLETO:\n{json.dumps(catalogo_disponible, indent=2)}\n"
    )

    if diseno_previo:
        system_prompt += (
            "\nESTADO: Modo Auto-corrección.\n"
            "El usuario está enviando una solicitud para modificar un diseño anterior.\n"
            "Analiza el JSON del diseño anterior provisto abajo, interpreta la orden del usuario "
            "y recalcula EXCLUSIVAMENTE los parámetros de posición Y o X de los componentes que lo requieran.\n"
            "Mantén intactos todos los demás componentes y SKUs."
        )
        prompt_usuario = f"DISEÑO ANTERIOR:\n{json.dumps(diseno_previo['matriz_ensamble_3d'])}\nCAMBIO: {comentario_usuario}"
        proxima_version = diseno_previo["version_actual"] + 1
        solicitud_inicial = diseno_previo["solicitud_original"]
        historial = diseno_previo.get("historial_comentarios", []) or []
        historial.append(comentario_usuario)
    else:
        system_prompt += (
            "\nESTADO: Modo Diseño Nuevo.\n"
            "Calcula la estructura de ensamble óptima desde cero basándote en los requerimientos del cliente."
        )
        prompt_usuario = f"Requerimiento: {comentario_usuario}"
        proxima_version = 1
        solicitud_inicial = comentario_usuario
        historial = []

    response = anthropic_client.messages.create(
        model="claude-3-5-sonnet-latest",
        max_tokens=3000,
        temperature=0,
        system=system_prompt,
        tools=[herramienta_guardar_diseno],
        tool_choice={"type": "tool", "name": "guardar_diseno_3d"},
        messages=[{"role": "user", "content": prompt_usuario}]
    )

    tool_calls = [c for c in response.content if c.type == "tool_use"]
    if not tool_calls:
        raise ValueError("Claude no pudo mapear de forma estructurada las coordenadas.")
        
    datos_ensamble = tool_calls[0].input

    supabase.table("disenos_racks").insert({
        "vendedor_id": vendedor_id,
        "session_id": session_id,
        "solicitud_original": solicitud_inicial,
        "version_actual": proxima_version,
        "matriz_ensamble_3d": datos_ensamble,
        "historial_comentarios": historial
    }).execute()

    return {"version": proxima_version, "variables": datos_ensamble}


# --- 4. GESTORES DE EVENTOS DE TELEGRAM ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje_inicio = (
        "📐 <b>Asistente de Racks 3D activo.</b>\n\n"
        "Dime qué necesitas (ej: un rack de 3 niveles para 1200kg) y armaré el diseño.\n"
        "Puedes interactuar conmigo enviando:\n"
        "1️⃣ Mensajes de texto directos o correcciones.\n"
        "2️⃣ Notas de voz explicando tu requerimiento.\n"
        "3️⃣ Fotos de requisiciones impresas o bosquejos.\n"
        "4️⃣ Archivos PDF con fichas técnicas o planos."
    )
    await update.message.reply_text(mensaje_inicio, parse_mode="HTML")


async def manejar_mensaje_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.effective_chat.id)
    vendedor_anon = f"Telegram_{update.effective_user.first_name}"
    mensaje_espera = await update.message.reply_text("📐 Calculando geometría 3D...")
    
    foto = update.message.photo
    documento = update.message.document
    texto = update.message.text
    voz = update.message.voice
    
    temp_path = ""
    texto_limpio = ""

    try:
        if texto:
            texto_limpio = texto
        elif voz:
            file = await context.bot.get_file(voz.file_id)
            temp_path = f"tg_temp_{voz.file_id}.ogg"
            await file.download_to_drive(temp_path)
            texto_limpio = transcribir_audio_groq(temp_path)
        elif documento:
            file = await context.bot.get_file(documento.file_id)
            extension = documento.file_name.split(".")[-1].lower()
            temp_path = f"tg_temp_{documento.file_name}"
            await file.download_to_drive(temp_path)
            texto_limpio = extraer_texto_pdf(temp_path) if extension == "pdf" else extraer_texto_imagen(temp_path)
        elif foto:
            file = await context.bot.get_file(foto[-1].file_id)
            temp_path = f"tg_temp_{foto[-1].file_id}.jpg"
            await file.download_to_drive(temp_path)
            texto_limpio = extraer_texto_imagen(temp_path)
        else:
            await mensaje_espera.edit_text("❌ Formato de mensaje no soportado.")
            return

        resultado = procesar_diseno_auto_correctivo(texto_limpio, session_id, vendedor_anon)
        version = resultado.get("version")
        datos = resultado.get("variables")
        
        matriz = datos.get("matriz_ensamble_3d") if datos.get("matriz_ensamble_3d") else datos
        vigas_list = matriz.get("vigas", [])
        vigas_resumen = "\n".join([f"  • Nivel {v.get('nivel')}: SKU <code>{v.get('sku')}</code> en Y={v.get('posicion', {}).get('y')}m" for v in vigas_list]) if vigas_list else "  • No se generaron componentes superiores en el cálculo."

        sb_url = os.getenv("SUPABASE_URL", "")
        sb_key = os.getenv("SUPABASE_KEY", "")
        
        encoded_url = urllib.parse.quote_plus(sb_url)
        encoded_key = urllib.parse.quote_plus(sb_key)
        
        link_autenticado = f"{URL_FRONTEND}?sb_url={encoded_url}&sb_key={encoded_key}&session_id={session_id}"

        transcripcion_html = f"🗣️ <b>Escuché:</b> <i>\"{texto_limpio}\"</i>\n\n" if voz else ""
        respuesta_html = (
            f"⚙️ <b>¡Diseño Listo! (Versión {version})</b>\n\n"
            f"{transcripcion_html}"
            f"📦 <b>Modelo:</b> {datos.get('tipo_rack')}\n"
            f"⚖️ <b>Carga:</b> {datos.get('peso_maximo_por_nivel_kg')} kg/nivel\n"
            f"🔢 <b>Niveles de Altura:</b> {datos.get('numero_niveles')}\n\n"
            f"🛠️ <b>Distribución de Vigas:</b>\n{vigas_resumen}\n\n"
            f"📝 <b>Notas:</b> {datos.get('comentarios_adicionales')}\n\n"
            f"🌐 <a href=\"{link_autenticado}\"><b>VER MODELO 3D EN TU VISOR</b></a>"
        )
        await mensaje_espera.edit_text(respuesta_html, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        await mensaje_espera.edit_text(f"❌ <b>Error:</b> {str(e)}", parse_mode="HTML")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# --- 5. DETECTORES OCR Y DE VOZ ---
def extraer_texto_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    return "".join([pagina.get_text() for pagina in doc])


def extraer_texto_imagen(file_path: str) -> str:
    return " ".join(ocr_reader.readtext(file_path, detail=0))


def transcribir_audio_groq(file_path: str) -> str:
    with open(file_path, "rb") as file:
        transcription = groq_client.audio.transcriptions.create(
            file=(os.path.basename(file_path), file.read()),
            model="whisper-large-v3",
            language="es",
            response_format="text"
        )
    return transcription


# --- 6. ENDPOINTS SEGUROS DE FASTAPI (RESUELVEN PERMISOS DEL NAVEGADOR) ---

def _candidate_bucket_names(bucket: str) -> list[str]:
    bucket = (bucket or "").strip()
    if not bucket:
        return []

    base = bucket.strip()
    variants = [
        base,
        base.lower(),
        base.replace(" ", "_"),
        base.replace(" ", "-"),
        base.replace(" ", ""),
        base.replace(" ", "").replace("_", "-"),
        base.replace(" ", "").replace("-", "_"),
    ]
    return list(dict.fromkeys([item for item in variants if item]))


def _candidate_folder_names(folder: str | None) -> list[str]:
    cleaned = (folder or "").strip().strip("/")
    if not cleaned:
        return [""]

    variants = [
        cleaned,
        cleaned.lower(),
        cleaned.replace(" ", "_"),
        cleaned.replace(" ", "-"),
        cleaned.replace(" ", ""),
        cleaned.replace(" ", "").replace("_", "-"),
        cleaned.replace(" ", "").replace("-", "_"),
        cleaned.replace(" ", "").replace("-", "_"),
        cleaned.replace(" ", "").replace("_", "-"),
        cleaned.replace(" ", "").replace("-", "_"),
        cleaned.replace(" ", "").replace("_", ""),
        cleaned.replace(" ", "").replace("-", ""),
    ]

    if "/" in cleaned:
        parts = [part for part in cleaned.split("/") if part]
        if parts:
            variants.append(parts[-1])
            variants.append(parts[-1].replace(" ", "_"))
            variants.append(parts[-1].replace(" ", "-"))
            variants.append("/".join(parts[:-1]))

    return list(dict.fromkeys([item for item in variants if item]))


def _build_public_url(bucket: str, relative_path: str) -> str:
    storage_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not storage_url:
        return ""
    encoded_bucket = urllib.parse.quote(bucket, safe="")
    encoded_path = urllib.parse.quote(relative_path, safe="")
    return f"{storage_url}/storage/v1/object/public/{encoded_bucket}/{encoded_path}"


def _get_storage_client():
    return supabase_service.storage


def _infer_modelo_files_from_catalogo(folder_prefix: str | None = None) -> list[dict]:
    if not folder_prefix:
        folder_prefix = ""

    storage_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    if not storage_url:
        return []

    try:
        resultado = supabase.table("catalogo_piezas").select("codigo_sku,nombre,url_modelo_glb").execute()
        rows = resultado.data or []
        archivos = []
        storage_client = _get_storage_client().from_("modelos")

        for row in rows:
            url = (row.get("url_modelo_glb") or "").strip()
            if not url or "/storage/v1/object/public/modelos/" not in url:
                continue

            if url.startswith(storage_url):
                relative_path = url.split("/storage/v1/object/public/modelos/", 1)[1]
            else:
                parsed = urllib.parse.urlparse(url)
                path = parsed.path or ""
                if "/storage/v1/object/public/modelos/" not in path:
                    continue
                relative_path = path.split("/storage/v1/object/public/modelos/", 1)[1]

            relative_path = urllib.parse.unquote(relative_path)
            if folder_prefix:
                prefix = folder_prefix.rstrip("/") + "/"
                if not relative_path.startswith(prefix):
                    continue

            name = os.path.basename(relative_path)
            if not name:
                continue

            folder = os.path.dirname(relative_path)
            if folder == ".":
                folder = ""

            size = 0
            mimetype = "model/3d"
            try:
                info = storage_client.info(relative_path)
                if isinstance(info, dict):
                    size = int(info.get("size", 0) or 0)
                    mimetype = info.get("content_type") or info.get("metadata", {}).get("content_type") or mimetype
            except Exception:
                pass

            archivos.append({
                "name": name,
                "bucket": "modelos",
                "folder": folder,
                "path": relative_path,
                "size": size,
                "type": mimetype,
                "url": url
            })

        return archivos
    except Exception:
        return []


def _normalize_storage_payload(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return payload.get("data") or payload.get("result") or []
    if hasattr(payload, "data"):
        return getattr(payload, "data") or []
    if hasattr(payload, "json"):
        try:
            parsed = payload.json()
            if isinstance(parsed, dict):
                return parsed.get("data") or parsed.get("result") or []
        except Exception:
            pass
    return []


def _normalize_storage_item(item: dict[str, any]) -> tuple[int, str]:
    size = item.get("size") or item.get("metadata", {}).get("size") or 0
    content_type = item.get("content_type") or item.get("metadata", {}).get("content_type") or item.get("metadata", {}).get("mimetype") or "archivo"
    try:
        size = int(size)
    except Exception:
        size = 0
    return size, content_type


def _listar_archivos_storage(bucket: str, folder: str | None = None) -> list[dict]:
    if not bucket:
        return []

    folder_prefix = (folder or "").strip().strip("/")
    candidates = []

    for candidate_bucket in _candidate_bucket_names(bucket):
        for candidate_folder in _candidate_folder_names(folder_prefix):
            candidates.append((candidate_bucket, candidate_folder))

    if folder_prefix:
        candidates.append((bucket, ""))
        candidates.append((bucket, folder_prefix))
        candidates.append((bucket, folder_prefix.replace(" ", "_")))
        candidates.append((bucket, folder_prefix.replace(" ", "-")))

    seen = set()
    ordered = []
    for pair in candidates:
        key = (pair[0].lower(), pair[1].lower())
        if key not in seen:
            seen.add(key)
            ordered.append(pair)

    for candidate_bucket, candidate_folder in ordered:
        try:
            payload = _get_storage_client().from_(candidate_bucket).list(candidate_folder)
            payload = _normalize_storage_payload(payload)
            if not isinstance(payload, list):
                continue

            archivos = []
            for item in payload:
                if not isinstance(item, dict):
                    continue

                name = item.get("name")
                if not name or name == ".emptyFolderPlaceholder":
                    continue

                relative_path = f"{candidate_folder}/{name}" if candidate_folder else name
                size, content_type = _normalize_storage_item(item)
                archivos.append({
                    "name": name,
                    "bucket": candidate_bucket,
                    "folder": candidate_folder,
                    "path": relative_path,
                    "size": size,
                    "type": content_type,
                    "url": _build_public_url(candidate_bucket, relative_path)
                })

            if archivos:
                return archivos
        except Exception:
            continue

    # Fallback: intentar leer la raíz del bucket directamente si no hay coincidencia de carpeta
    for candidate_bucket in _candidate_bucket_names(bucket):
        try:
            payload = _get_storage_client().from_(candidate_bucket).list("")
            if isinstance(payload, list):
                archivos = []
                for item in payload:
                    if not isinstance(item, dict):
                        continue
                    name = item.get("name")
                    if not name or name == ".emptyFolderPlaceholder":
                        continue
                    size, content_type = _normalize_storage_item(item)
                    archivos.append({
                        "name": name,
                        "bucket": candidate_bucket,
                        "folder": "",
                        "path": name,
                        "size": size,
                        "type": content_type,
                        "url": _build_public_url(candidate_bucket, name)
                    })
                if archivos:
                    return archivos
        except Exception:
            continue

    if bucket == "modelos":
        archivos = _infer_modelo_files_from_catalogo(folder_prefix)
        if archivos:
            return archivos

    return []


@app.get("/storage/files")
def obtener_archivos_storage(bucket: str = "modelos", folder: str = ""):
    """Lista archivos del storage de Supabase desde el backend para evitar restricciones del navegador."""
    try:
        print(f"[storage/files] request bucket={bucket!r} folder={folder!r}")
        archivos = _listar_archivos_storage(bucket, folder)
        print(f"[storage/files] found {len(archivos)} files for bucket={bucket!r} folder={folder!r}")
        return {"bucket": bucket, "folder": folder or "", "files": archivos}
    except Exception as exc:
        print(f"[storage/files] error: {exc}")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/storage/files/replace")
async def replace_storage_file(
    bucket: str = Form(...),
    path: str = Form(...),
    file: UploadFile = File(...)
):
    """Reemplaza un archivo existente en Supabase Storage con un nuevo archivo Draco."""
    try:
        contents = await file.read()
        service_client = supabase_service if supabase_service else supabase
        service_client.storage.from_(bucket).upload(
            path=path,
            file=contents,
            file_options={"cache-control": "3600", "upsert": "true"}
        )
        return {"status": "success", "bucket": bucket, "path": path, "size": len(contents)}
    except Exception as exc:
        error_message = str(exc)
        if hasattr(exc, 'args') and exc.args:
            error_message = exc.args[0]
        raise HTTPException(status_code=500, detail=error_message) from exc


@app.post("/storage/files/optimize")
async def optimize_storage_file(
    bucket: str = Form(...),
    path: str = Form(...),
    encoder_method: str = Form("edgebreaker")
):
    """Descarga un .glb desde Storage, lo comprime con glTF-Transform (Draco) y lo vuelve a subir.

    Requiere que `node` esté disponible en el servidor y permite usar `npx @gltf-transform/cli draco`.
    """
    service_client = supabase_service if supabase_service else supabase
    try:
        public_url = _build_public_url(bucket, path)
        if not public_url:
            raise ValueError("No se pudo construir la URL pública del archivo.")

        # 1) Descargar el archivo original (intenta URL pública; si falla, intenta descarga con cliente de servicio)
        try:
            with urllib.request.urlopen(public_url, timeout=30) as resp:
                original_bytes = resp.read()
        except Exception as download_err:
            print(f"[optimize] descarga pública falló: {download_err}; intentando descarga con cliente de servicio...")
            # Intentar descarga privada usando el cliente service (si está disponible)
            try:
                storage_client = service_client.storage.from_(bucket)
                download_payload = storage_client.download(path)
                if isinstance(download_payload, (bytes, bytearray)):
                    original_bytes = bytes(download_payload)
                elif hasattr(download_payload, 'read'):
                    original_bytes = download_payload.read()
                elif isinstance(download_payload, dict) and download_payload.get('data'):
                    original_bytes = download_payload.get('data')
                else:
                    raise Exception('Formato de respuesta inesperado del cliente de storage al descargar')
            except Exception as svc_err:
                print(f"[optimize] descarga via cliente de servicio falló: {svc_err}")
                raise HTTPException(status_code=500, detail=f"Error descargando el archivo: {download_err} | {svc_err}") from svc_err

        # 2) Escribir archivo temporal de entrada y salida
        tmp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
        tmp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".glb")
        try:
            tmp_in.write(original_bytes)
            tmp_in.flush()
            tmp_in.close()
            tmp_out.close()

            # 3) Ejecutar la herramienta Node (glTF-Transform CLI) vía npx
            # Prefer a locally installed binary in backend/node_modules/.bin if available,
            # otherwise fall back to npx for ad-hoc execution.
            local_bin_unix = os.path.join(os.path.dirname(__file__), 'node_modules', '.bin', 'gltf-transform')
            local_bin_cmd = local_bin_unix + ('.cmd' if os.name == 'nt' else '')
            bin_path = None
            if os.path.exists(local_bin_cmd):
                bin_path = local_bin_cmd
            elif os.path.exists(local_bin_unix):
                bin_path = local_bin_unix

            if bin_path:
                cmd = [bin_path, 'draco', tmp_in.name, tmp_out.name, '--encoder-method', encoder_method]
            else:
                cmd = [
                    'npx',
                    '@gltf-transform/cli',
                    'draco',
                    tmp_in.name,
                    tmp_out.name,
                    '--encoder-method',
                    encoder_method
                ]
            try:
                print(f"[optimize] running command: {cmd}")
                proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
            except subprocess.CalledProcessError as cpe:
                stderr = cpe.stderr or ""
                raise HTTPException(status_code=500, detail=f"Compresión fallida: {stderr}") from cpe
            except subprocess.TimeoutExpired as toe:
                raise HTTPException(status_code=500, detail=f"Tiempo de compresión agotado: {toe}") from toe
            except FileNotFoundError as fnf:
                msg = (
                    "Herramienta de compresión no encontrada. Asegúrate de tener Node.js y npm instalados "
                    "y ejecuta `npm install` en la carpeta backend para instalar @gltf-transform/cli. "
                    f"Detalle: {fnf}"
                )
                print(f"[optimize] FileNotFoundError: {fnf}")
                raise HTTPException(status_code=500, detail=msg) from fnf

            # 4) Leer archivo comprimido y subirlo reemplazando el original
            with open(tmp_out.name, "rb") as f:
                compressed_bytes = f.read()

            service_client.storage.from_(bucket).upload(
                path=path,
                file=compressed_bytes,
                file_options={"cache-control": "3600", "upsert": "true"}
            )

            return {
                "status": "success",
                "bucket": bucket,
                "path": path,
                "original_size": len(original_bytes),
                "compressed_size": len(compressed_bytes)
            }
        finally:
            # Cleanup temporal
            try:
                if os.path.exists(tmp_in.name):
                    os.remove(tmp_in.name)
            except Exception:
                pass
            try:
                if os.path.exists(tmp_out.name):
                    os.remove(tmp_out.name)
            except Exception:
                pass

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/storage/upload")
async def upload_training_file(file: UploadFile = File(...)):
    """
    Sube archivos de forma segura desde el backend al Storage de Supabase,
    analiza el texto según su tipo (PDF/Imagen/TXT) y lo almacena para contextualizar la IA.
    """
    try:
        contents = await file.read()
        filename_sanitizado = f"{int(asyncio.get_event_loop().time())}_{file.filename}"
        path_storage = f"entrenamiento/{filename_sanitizado}"

        # 1. Subir al storage usando credenciales de servicio del servidor
        supabase.storage.from_("modelos").upload(
            path=path_storage,
            file=contents,
            file_options={"cache-control": "3600", "upsert": "true"}
        )

        # 2. Procesamiento y extracción de texto
        texto_extraido = ""
        temp_file_path = f"temp_{filename_sanitizado}"
        with open(temp_file_path, "wb") as f:
            f.write(contents)

        try:
            ext = file.filename.split(".")[-1].lower()
            if ext == "pdf":
                texto_extraido = extraer_texto_pdf(temp_file_path)
            elif ext in ["png", "jpg", "jpeg"]:
                texto_extraido = extraer_texto_imagen(temp_file_path)
            elif ext == "txt":
                with open(temp_file_path, "r", encoding="utf-8", errors="ignore") as txt_f:
                    texto_extraido = txt_f.read()
        except Exception as ocr_err:
            texto_extraido = f"Error de OCR/Lectura: {str(ocr_err)}"
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

        # 3. Guardar registro histórico en la base de datos
        supabase.table("cotizaciones").insert({
            "vendedor_id": "System_CAD_Backend",
            "tipo_archivo": file.filename.split('.')[-1].upper(),
            "texto_extraido": texto_extraido or f"Archivo subido: {file.filename}",
            "variables_json": {
                "filename": filename_sanitizado,
                "original_name": file.filename,
                "size": len(contents)
            }
        }).execute()

        return {"status": "success", "filename": filename_sanitizado}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/storage/files/{filename}")
async def delete_storage_file(filename: str):
    """
    Elimina un archivo del storage 'modelos/entrenamiento' y remueve su registro de la DB
    utilizando credenciales del lado del servidor de forma segura.
    """
    try:
        # 1. Eliminar archivo del Storage
        supabase.storage.from_("modelos").remove([f"entrenamiento/{filename}"])

        # 2. Eliminar registro del historial en la DB
        supabase.table("cotizaciones").delete().filter("variables_json->>filename", "eq", filename).execute()

        return {"status": "success", "message": f"Archivo {filename} eliminado de forma segura."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    return {"status": "healthy", "service": "RackBuilder 3D API"}