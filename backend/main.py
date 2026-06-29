import os
import fitz  # PyMuPDF
import easyocr
import json
import asyncio
import urllib.parse  # Para codificar de forma segura las credenciales en la URL
import urllib.request
import urllib.error
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
load_dotenv()

# Inicializaciones de clientes de APIs y Base de Datos
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
ocr_reader = easyocr.Reader(['es'])
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# URL de tu visualizador alojado en GitHub Pages (apuntando al archivo explícito)
URL_FRONTEND = "https://dazaragoza-ti.github.io/cotizacion_IA/index.html"

def _normalizar_candidatos_bucket(bucket: str) -> list[str]:
    bucket = (bucket or "").strip()
    if not bucket:
        return []

    base = bucket.lower().strip()
    alternates = [
        bucket,
        base,
        base.replace(" ", "_"),
        base.replace(" ", "-"),
        base.replace(" ", ""),
        base.replace(" ", "").replace("_", "-"),
        base.replace(" ", "").replace("-", "_"),
    ]
    return list(dict.fromkeys([item for item in alternates if item]))


def listar_archivos_storage(bucket: str, folder: str | None = None) -> list[dict]:
    storage_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    api_key = (
        os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE")
        or os.getenv("SUPABASE_KEY")
    )

    if not storage_url or not api_key:
        raise RuntimeError("No hay configuración de Supabase para consultar Storage")

    folder_prefix = (folder or "").strip().strip("/")
    candidates = _normalizar_candidatos_bucket(bucket)

    for candidate_bucket in candidates:
        url = f"{storage_url}/storage/v1/object/list/{urllib.parse.quote(candidate_bucket, safe='')}"
        if folder_prefix:
            url += f"?prefix={urllib.parse.quote(folder_prefix, safe='')}"

        request = urllib.request.Request(
            url,
            headers={
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
                if isinstance(payload, list):
                    archivos = []
                    for item in payload:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("name")
                        if not name or name == ".emptyFolderPlaceholder":
                            continue
                        relative_path = f"{folder_prefix}/{name}" if folder_prefix else name
                        archivos.append({
                            "name": name,
                            "bucket": candidate_bucket,
                            "folder": folder_prefix,
                            "path": relative_path,
                            "size": item.get("metadata", {}).get("size", 0),
                            "type": item.get("metadata", {}).get("mimetype", "archivo"),
                            "url": f"{storage_url}/storage/v1/object/public/{candidate_bucket}/{urllib.parse.quote(relative_path, safe='')}"
                        })
                    return archivos
        except urllib.error.HTTPError as exc:
            if exc.code not in (401, 403, 404):
                raise
            continue
        except Exception:
            continue

    return []


@app.get("/storage/files")
def obtener_archivos_storage(bucket: str, folder: str | None = None):
    try:
        archivos = listar_archivos_storage(bucket, folder)
        return {"bucket": bucket, "folder": folder or "", "files": archivos}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
    Si es la primera interacción, retorna None de forma segura.
    """
    try:
        resultado = supabase.table("disenos_racks").select("*").eq("session_id", session_id).order("version_actual", desc=True).limit(1).execute()
        return resultado.data[0] if resultado.data else None
    except Exception:
        return None

def procesar_diseno_auto_correctivo(comentario_usuario: str, session_id: str, vendedor_id: str) -> dict:
    """
    Lógica del Agente de Ensamble:
    - Base de Diseño: Toma el modelo pre-armado '(-)_RACK_180X61X151' (de 1.80m de ancho x 0.61m de prof x 1.51m de alto) como el plano dimensional maestro.
    - Modularización y Recreación: Cuando el usuario pide estructurar el rack a partir de piezas individuales o expandir niveles superiores,
      la IA utilizará los marcos 'CABECERA_302X91_CON_TRAVESANO' y acoplará las vigas mediante las ménsulas 'MENSULA_GOTA_CARGA_LIGERA_DERECHA'
      replicando la alineación, cotas y el ancho exacto del modelo base original.
    """
    catalogo_disponible = consultar_catalogo_piezas()
    diseno_previo = obtener_ultimo_diseno(session_id)

    # Estructura limpia de componentes en la raíz del ensamble
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

    # REGLAS GEOMÉTRICAS MAESTRAS BASADAS EN TU RACK DE REFERENCIA:
    system_prompt = (
        "Eres un Ingeniero CAD Senior especializado en modelado espacial de racks industriales en 3D.\n"
        "Tu única tarea es calcular la colocación de componentes físicos en metros (ejes X, Y, Z).\n\n"
        "MODELO BLUEPRINT DE REFERENCIA:\n"
        "- '(-)_RACK_180X61X151': Módulo completo pre-ensamblado de 1 nivel. Mide exactamente 1.80m de largo (ancho), 1.51m de alto, 0.61m de profundidad.\n"
        "  • El ancho útil del rack de referencia es de 1.80 metros (las cabeceras están separadas por esa distancia).\n"
        "  • El fondo del rack de referencia es de 0.61 metros.\n\n"
        "REGLAS DE RECREACIÓN MODULAR COMPONENTES REALES:\n"
        "- 'CABECERA_302X91_CON_TRAVESANO': Marco estructural lateral de 3.02m de altura, 0.91m de profundidad.\n"
        "- 'MENSULA_GOTA_CARGA_LIGERA_DERECHA': Ménsula de acople drop-lock de carga ligera.\n"
        "- 'VIGA-2000' (u otra del catálogo de longitud aproximada a 1.80m):\n\n"
        "INSTRUCCIONES DE CONSTRUCCIÓN:\n"
        "1. Si el usuario solicita un rack de un solo nivel, utiliza directamente el modelo pre-armado '(-)_RACK_180X61X151' posicionado en X=0, Y=0, Z=0.\n"
        "2. Si el usuario solicita un rack modular extendido, o requiere expandir el diseño agregando más niveles de carga:\n"
        "  • Utiliza dos cabeceras 'CABECERA_302X91_CON_TRAVESANO' como soportes laterales colocados a los lados. Para respetar el ancho del rack base de 1.80 metros, sitúa la cabecera izquierda en X = -0.9 y la cabecera derecha en X = 0.9.\n"
        "  • Coloca las vigas horizontales superiores a lo largo de las alturas Y deseadas (ej: nivel 1 en Y=0.8, nivel 2 en Y=1.8, nivel 3 en Y=2.7).\n"
        "  • En cada extremo lateral de enganche de las vigas superiores, coloca las ménsulas 'MENSULA_GOTA_CARGA_LIGERA_DERECHA' (posicionadas a la misma altura Y de la viga del nivel, en X = -0.9 para el extremo izquierdo y X = 0.9 para el extremo derecho) para simular de forma impecable el acople físico de fábrica.\n\n"
        f"INVENTARIO TÉCNICO COMPLETO EN SUPABASE:\n{json.dumps(catalogo_disponible, indent=2)}\n"
    )

    if diseno_previo:
        system_prompt += (
            "\nESTADO: Modo Auto-corrección.\n"
            "El usuario está enviando una solicitud para modificar un diseño anterior.\n"
            "Analiza el JSON del diseño anterior provisto abajo, interpreta la orden del usuario "
            "y recalcula EXCLUSIVAMENTE los parámetros de posición Y o X de los componentes que lo requieran.\n"
            "Conserva la relación de alineación de 1.80m de ancho basada en '(-)_RACK_180X61X151' y ajusta solo lo necesario."
        )
        prompt_usuario = f"DISEÑO ANTERIOR:\n{json.dumps(diseno_previo['matriz_ensamble_3d'])}\nCAMBIO: {comentario_usuario}"
        proxima_version = diseno_previo["version_actual"] + 1
        solicitud_inicial = diseno_previo["solicitud_original"]
        historial = diseno_previo.get("historial_comentarios", []) or []
        historial.append(comentario_usuario)
    else:
        system_prompt += (
            "\nESTADO: Modo Diseño Nuevo.\n"
            "Calcula la estructura de ensamble óptima desde cero utilizando el rack base '(-)_RACK_180X61X151' en X=0, Y=0, Z=0 como primer nivel obligatorio, "
            "y apila las cabeceras de 3m, vigas superiores y ménsulas adicionales si se requieren niveles superiores."
        )
        prompt_usuario = f"Requerimiento: {comentario_usuario}"
        proxima_version = 1
        solicitud_inicial = comentario_usuario
        historial = []

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
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

    usage = {}
    if hasattr(response, "usage"):
        usage = response.usage or {}
    elif isinstance(response, dict):
        usage = response.get("usage", {}) or {}
    elif hasattr(response, "get"):
        usage = response.get("usage", {}) or {}

    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
    else:
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0

    supabase.table("disenos_racks").insert({
        "vendedor_id": vendedor_id,
        "session_id": session_id,
        "solicitud_original": solicitud_inicial,
        "version_actual": proxima_version,
        "matriz_ensamble_3d": datos_ensamble,
        "historial_comentarios": historial,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens
    }).execute()

    return {"version": proxima_version, "variables": datos_ensamble}

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
        
        # Soportar que la matriz de componentes esté en la raíz o anidada
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

app = FastAPI(lifespan=lifespan)