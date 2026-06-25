import os
import fitz  # PyMuPDF
import easyocr
import json
import asyncio
import urllib.parse
from fastapi import FastAPI, UploadFile, File, Form
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

# URL de tu visualizador alojado en GitHub Pages
URL_FRONTEND = "https://dazaragoza-ti.github.io/cotizacion_IA/"

def consultar_catalogo_piezas() -> list:
    """
    Trae el inventario de componentes reales disponibles de Supabase.
    Si la tabla está vacía, no existe, o la consulta falla, provee un catálogo técnico
    con valores de ingeniería por defecto para evitar que Claude se quede sin contexto de diseño.
    """
    fallback_piezas = [
        {"sku": "VIGA-LIG-2400", "nombre": "Viga Ligera 2.4m", "tipo": "viga", "longitud_metros": 2.4, "peso_maximo_soportado_kg": 800},
        {"sku": "VIGA-PES-2400", "nombre": "Viga Pesada 2.4m", "tipo": "viga", "longitud_metros": 2.4, "peso_maximo_soportado_kg": 2200},
        {"sku": "MARCO-ALT-4000", "nombre": "Marco Estructural 4m", "tipo": "marco", "altura_metros": 4.0, "profundidad_metros": 1.0},
        {"sku": "MENSULA-ESTANDAR", "nombre": "Ménsula de Ensamble", "tipo": "mensula"}
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
    1. Si no existe un diseño previo, calcula y genera un ensamble desde cero.
    2. Si existe un diseño previo, Claude toma las coordenadas espaciales del JSON anterior y
       recalcula únicamente los componentes afectados por el comentario del usuario (Memoria de Diseño).

    FIX: El tool ahora guarda los componentes (marcos, vigas, mensulas) dentro de
    "matriz_ensamble_3d" como objeto anidado, en lugar de en la raíz. Esto unifica
    el schema con el que espera el frontend en renderRack().
    """
    catalogo_disponible = consultar_catalogo_piezas()
    diseno_previo = obtener_ultimo_diseno(session_id)

    # FIX #1: Schema del tool corregido — componentes anidados dentro de "matriz_ensamble_3d"
    # para que coincidan exactamente con lo que el frontend espera en renderRack().
    herramienta_guardar_diseno = {
        "name": "guardar_diseno_3d",
        "description": "Registra la matriz y geometría de ensamble 3D del rack.",
        "input_schema": {
            "type": "object",
            "properties": {
                "tipo_rack": {"type": "string"},
                "peso_maximo_por_nivel_kg": {"type": "number"},
                "numero_niveles": {"type": "integer"},
                "comentarios_adicionales": {"type": "string"},
                # Los componentes 3D van ANIDADOS en este objeto
                "matriz_ensamble_3d": {
                    "type": "object",
                    "properties": {
                        "marcos": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "sku": {"type": "string"},
                                    "posicion": {
                                        "type": "object",
                                        "properties": {
                                            "x": {"type": "number"},
                                            "y": {"type": "number"},
                                            "z": {"type": "number"}
                                        },
                                        "required": ["x", "y", "z"]
                                    }
                                },
                                "required": ["sku", "posicion"]
                            }
                        },
                        "vigas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "sku": {"type": "string"},
                                    "nivel": {"type": "integer"},
                                    "posicion": {
                                        "type": "object",
                                        "properties": {
                                            "x": {"type": "number"},
                                            "y": {"type": "number"},
                                            "z": {"type": "number"}
                                        },
                                        "required": ["x", "y", "z"]
                                    }
                                },
                                "required": ["sku", "nivel", "posicion"]
                            }
                        },
                        "mensulas": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "sku": {"type": "string"},
                                    "nivel": {"type": "integer"},
                                    "lado": {"type": "string", "enum": ["izq", "der"]},
                                    "posicion": {
                                        "type": "object",
                                        "properties": {
                                            "x": {"type": "number"},
                                            "y": {"type": "number"},
                                            "z": {"type": "number"}
                                        },
                                        "required": ["x", "y", "z"]
                                    }
                                },
                                "required": ["sku", "nivel", "lado", "posicion"]
                            }
                        }
                    },
                    "required": ["marcos", "vigas", "mensulas"]
                }
            },
            "required": ["tipo_rack", "peso_maximo_por_nivel_kg", "numero_niveles", "matriz_ensamble_3d", "comentarios_adicionales"]
        }
    }

    system_prompt = (
        "Eres un Ingeniero CAD Senior especializado en modelado espacial de racks industriales en 3D.\n"
        "Tu única tarea es calcular la colocación y rotación de componentes físicos en metros (ejes X, Y, Z).\n\n"
        "REGLAS GEOMÉTRICAS CLAVE:\n"
        "- Eje Y representa la altura. Las vigas de cada nivel deben espaciarse uniformemente (ej: nivel 1 en Y=0.8, nivel 2 en Y=1.8, etc.).\n"
        "- Eje X representa el ancho. El marco izquierdo se sitúa en X = -1.2, y el marco derecho en X = 1.2.\n"
        "- Las vigas horizontales deben centrarse en X = 0.\n"
        "- Las ménsulas de acople deben situarse exactamente sobre los marcos (ej: en X = -1.2 para el lado izquierdo y X = 1.2 para el derecho) a la misma altura Y de la viga del nivel.\n\n"
        f"INVENTARIO DISPONIBLE EN SUPABASE:\n{json.dumps(catalogo_disponible, indent=2)}\n"
    )

    if diseno_previo:
        system_prompt += (
            "\nESTADO: Modo Auto-corrección.\n"
            "El usuario está enviando una solicitud para modificar un diseño anterior.\n"
            "Analiza el JSON del diseño anterior provisto abajo, interpreta la orden del usuario "
            "y recalcula EXCLUSIVAMENTE los parámetros de posición Y o X de los componentes que lo requieran.\n"
            "Mantén intactos todos los demás componentes y SKUs."
        )
        # FIX #2: Leer correctamente la matriz del diseño previo (puede estar anidada o en raíz)
        matriz_previa = diseno_previo.get("matriz_ensamble_3d", {})
        prompt_usuario = f"DISEÑO ANTERIOR:\n{json.dumps(matriz_previa)}\nCAMBIO: {comentario_usuario}"
        proxima_version = diseno_previo["version_actual"] + 1
        solicitud_inicial = diseno_previo["solicitud_original"]
        historial = diseno_previo.get("historial_comentarios", []) or []
        historial.append(comentario_usuario)
    else:
        system_prompt += (
            "\nESTADO: Modo Diseño Nuevo.\n"
            "Calcula la estructura de ensamble óptima desde cero."
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

    # FIX #3: Guardar el objeto completo que devuelve Claude (ya incluye matriz_ensamble_3d anidada)
    # en la columna "matriz_ensamble_3d" de Supabase para que el frontend lo lea correctamente.
    supabase.table("disenos_racks").insert({
        "vendedor_id": vendedor_id,
        "session_id": session_id,
        "solicitud_original": solicitud_inicial,
        "version_actual": proxima_version,
        "matriz_ensamble_3d": datos_ensamble,   # ← objeto completo con matriz anidada
        "historial_comentarios": historial
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
            await mensaje_espera.edit_text("❌ Formato no soportado.")
            return

        resultado = procesar_diseno_auto_correctivo(texto_limpio, session_id, vendedor_anon)
        version = resultado.get("version")
        datos = resultado.get("variables")

        # FIX #4: Leer vigas del lugar correcto (dentro de matriz_ensamble_3d)
        matriz = datos.get("matriz_ensamble_3d", {})
        vigas_list = matriz.get("vigas", [])
        vigas_resumen = "\n".join([
            f"  • Nivel {v.get('nivel')}: SKU <code>{v.get('sku')}</code> en Y={v.get('posicion', {}).get('y')}m"
            for v in vigas_list
        ])

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