import os
import fitz  # PyMuPDF
import easyocr
import json
import asyncio
from fastapi import FastAPI, UploadFile, File, Form
from supabase import create_client, Client
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

# Importaciones para el Bot de Telegram
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# 1. Asegurar la carga de variables antes de cualquier inicialización
load_dotenv()

# --- CONFIGURACIÓN E INICIALIZACIONES ---
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
ocr_reader = easyocr.Reader(['es'])
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# URL de tu visualizador en GitHub Pages
URL_FRONTEND = "https://dazaragoza-ti.github.io/cotizacion_IA/"

class EstructuraAlmacen(BaseModel):
    tipo_rack: str
    peso_maximo_por_nivel_kg: float
    numero_niveles: int
    ancho_pasillo_maniobra_metros: float | None = None
    comentarios_adicionales: str

# --- FUNCIONES CORE DE PROCESAMIENTO ---
def extraer_texto_pdf(file_path: str) -> str:
    doc = fitz.open(file_path)
    return "".join([pagina.get_text() for pagina in doc])

def extraer_texto_imagen(file_path: str) -> str:
    return " ".join(ocr_reader.readtext(file_path, detail=0))

def procesar_e_ingestar_logica(texto_limpio: str, tipo_archivo: str, vendedor_id: str) -> dict:
    """Función unificada que llama a Groq e inserta en Supabase"""
    if not texto_limpio.strip():
        raise ValueError("No se pudo extraer texto del archivo.")

    # Llamada a Groq
    chat_completion = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": f"Eres un ingeniero experto en racks industriales. Extrae los datos solicitados en formato JSON cumpliendo estrictamente con este esquema: {EstructuraAlmacen.model_json_schema()}"
            },
            {"role": "user", "content": f"Texto extraído: {texto_limpio}"}
        ],
        response_format={"type": "json_object"},
        temperature=0
    )
    
    variables_finales = json.loads(chat_completion.choices[0].message.content)
    
    # Guardar en Supabase
    supabase.table("cotizaciones").insert({
        "vendedor_id": vendedor_id,
        "tipo_archivo": tipo_archivo,
        "texto_extraido": texto_limpio,
        "variables_json": variables_finales
    }).execute()
    
    return variables_finales


# --- CONTROLADORES DEL BOT DE TELEGRAM ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Hola! Soy el asistente de Racks Industriales 🤖📦.\n\n"
        "Envíame una foto de un plano o un archivo PDF técnico y extraeré "
        "automáticamente las variables para renderizar el modelo 3D en tiempo real."
    )

async def manejar_documento_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje_espera = await update.message.reply_text("📥 Recibiendo archivo... Procesando con Inteligencia Artificial, por favor espera.")
    
    foto = update.message.photo
    documento = update.message.document
    
    temp_path = ""
    tipo_archivo = ""
    
    try:
        if documento:
            file = await context.bot.get_file(documento.file_id)
            extension = documento.file_name.split(".")[-1].lower()
            temp_path = f"tg_temp_{documento.file_name}"
            tipo_archivo = "pdf" if extension == "pdf" else "imagen"
        elif foto:
            file = await context.bot.get_file(foto[-1].file_id)
            temp_path = f"tg_temp_{foto[-1].file_id}.jpg"
            tipo_archivo = "imagen"
        else:
            await mensaje_espera.edit_text("❌ Formato no soportado. Envía un PDF o una Imagen.")
            return

        # Descargar archivo localmente
        await file.download_to_drive(temp_path)
        
        # Extraer Texto según el formato
        if tipo_archivo == "pdf":
            texto_limpio = extraer_texto_pdf(temp_path)
        else:
            texto_limpio = extraer_texto_imagen(temp_path)
            
        # Ejecutar lógica asignando nombre dinámico del usuario de Telegram
        vendedor_anon = f"Telegram_{update.effective_user.first_name}"
        res_json = procesar_e_ingestar_logica(texto_limpio, tipo_archivo, vendedor_anon)
        
        # Respuesta estructurada con link directo a GitHub Pages en Markdown
        respuesta_bonita = (
            "✅ **¡Archivo Procesado y Guardado!**\n\n"
            f"📦 **Tipo de Rack:** {res_json.get('tipo_rack')}\n"
            f"🔢 **Niveles:** {res_json.get('numero_niveles')}\n"
            f"⚖️ **Peso Máx p/ Nivel:** {res_json.get('peso_maximo_por_nivel_kg')} kg\n"
            f"📏 **Pasillo Maniobra:** {res_json.get('ancho_pasillo_maniobra_metros') or 'No especificado'} m\n\n"
            f"📝 **Comentarios:** {res_json.get('comentarios_adicionales')}\n\n"
            f"🌐 [¡VER MODELO 3D EN VIVO AQUÍ!]({URL_FRONTEND})"
        )
        await mensaje_espera.edit_text(respuesta_bonita, parse_mode="Markdown")

    except Exception as e:
        await mensaje_espera.edit_text(f"❌ Ocurrió un error al procesar el archivo:\n`{str(e)}`", parse_mode="Markdown")
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# --- CICLO DE VIDA DE FASTAPI (Asíncrono para el Bot) ---
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Código ejecutado al encender el servidor
    tg_app = Application.builder().token(BOT_TOKEN).build()
    tg_app.add_handler(CommandHandler("start", start_command))
    tg_app.add_handler(MessageHandler(filters.Document.ALL | filters.PHOTO, manejar_documento_telegram))
    
    await tg_app.initialize()
    await tg_app.start()
    await tg_app.updater.start_polling()
    
    print("🤖 Bot de Telegram escuchando con éxito...")
    yield
    # Código ejecutado al apagar el servidor
    await tg_app.updater.stop()
    await tg_app.stop()
    await tg_app.shutdown()

# Inicialización de FastAPI vinculando el ciclo de vida anterior
app = FastAPI(lifespan=lifespan)


# --- ENDPOINT HTTP (Para compatibilidad web e interfaz de Swagger Docs) ---
@app.post("/ingestar")
async def ingestar_archivo(vendedor_id: str = Form(...), file: UploadFile = File(...)):
    temp_path = f"temp_{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        extension = file.filename.split(".")[-1].lower()
        texto_limpio = extraer_texto_pdf(temp_path) if extension == "pdf" else extraer_texto_imagen(temp_path)
        tipo = "pdf" if extension == "pdf" else "imagen"
        
        variables_finales = procesar_e_ingestar_logica(texto_limpio, tipo, vendedor_id)
        
        return {
            "status": "Procesado con éxito por Llama 3.3 en Groq",
            "datos_guardados_en_supabase": variables_finales
        }
    except Exception as e:
        return {"status": "Error Interno", "detalles_del_error": str(e)}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)