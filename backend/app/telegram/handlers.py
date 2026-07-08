"""
Handler de Telegram — flujo único unificado.

Ya no hay dos modos que alternar (/rack vs /proyecto). Todo mensaje pasa por
el mismo camino: visión directa a Claude (imágenes/PDF sin OCR), cuestionario
interactivo si falta algo crítico, validador estructural completo, pipeline
determinista (modelo 3D real + PDF de 4 hojas + XLSX), y el mismo visor 3D
de GitHub Pages que antes solo tenía el agente rápido (vía adaptador_visor).

Es la fusión de lo mejor de los dos modos que existían antes:
  - Del agente rápido: el visor 3D de GitHub Pages y el versionado por sesión.
  - Del proyectista PM: visión, cuestionario, validador y despiece/cotización reales.
"""
import os
import asyncio
import logging
from io import BytesIO

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from ..services.ocr_service import transcribir_audio_groq, comprimir_imagen, describir_imagen_groq
from ..services.proyecto_pm_service import generar_proyecto_pm, limpiar_temporales
from ..ai.pipelines import cuestionario

log = logging.getLogger("telegram.handlers")

# Adjuntos pendientes por sesión — Claude los recibe como imágenes/PDF de
# verdad, sin pasar por OCR. Se pierde si el proceso se reinicia.
BUFFERS: dict[str, dict] = {}


def _buf(session_id: str) -> dict:
    return BUFFERS.setdefault(session_id, {"imagenes": [], "pdfs": [], "capciones": []})


async def _agregar_imagen(buf: dict, mime: str, data: bytes) -> None:
    """
    Comprime la imagen (baja tokens de Claude) y le pide a Groq una
    descripción corta (rápida y barata) que se agrega como contexto de
    texto — ayuda a Claude a orientarse sin tener que "pensar" tanto sobre
    cada imagen desde cero, y sirve de respaldo si el .glb/token budget
    aprieta.
    """
    mime_comprimido, data_comprimida = await asyncio.to_thread(comprimir_imagen, data)
    buf["imagenes"].append((mime_comprimido, data_comprimida))
    caption = await asyncio.to_thread(describir_imagen_groq, data_comprimida, mime_comprimido)
    if caption:
        buf["capciones"].append(caption)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje_inicio = (
        "🏗️ <b>Proyectista de Racks PM La Piedad</b>\n\n"
        "Mándame el requerimiento del cliente y te entrego diseño, despiece, "
        "cotización, planos PDF, XLSX y el modelo 3D en tu visor.\n\n"
        "Puedes mandarme:\n"
        "1️⃣ Mensajes de texto directos o correcciones.\n"
        "2️⃣ Notas de voz explicando el requerimiento.\n"
        "3️⃣ Fotos de requisiciones, bosquejos o del sitio.\n"
        "4️⃣ Archivos PDF con planos o fichas técnicas.\n\n"
        "Si falta algo crítico (producto, dimensiones, unidad de carga, "
        "montacargas), te voy preguntando antes de cotizar.\n\n"
        "<code>/cancelar</code> — abandona el cuestionario en curso."
    )
    await update.message.reply_text(mensaje_inicio, parse_mode="HTML")


async def cancelar_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.effective_chat.id)
    BUFFERS.pop(session_id, None)
    cuestionario.limpiar(update.effective_user.id)
    await update.message.reply_text(
        "❎ Cuestionario cancelado. Cuando quieras empezar de nuevo, mándame los datos del proyecto."
    )


_FORMATOS_IMAGEN_ACEPTADOS = {"image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"}


async def manejar_mensaje_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session_id = str(update.effective_chat.id)
    uid = update.effective_user.id
    user = update.effective_user
    msg = update.message
    buf = _buf(session_id)

    foto = msg.photo
    documento = msg.document
    texto = msg.text
    voz = msg.voice

    # --- Nota de voz: se transcribe y se trata como la petición ---
    if voz:
        temp_path = f"tg_temp_{voz.file_id}.ogg"
        try:
            file = await context.bot.get_file(voz.file_id)
            await file.download_to_drive(temp_path)
            texto_voz = transcribir_audio_groq(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        await _procesar(update, context, session_id, uid, user, texto_voz)
        return

    # --- Foto/documento: se guardan comprimidos + descritos por Groq, no OCR ---
    if foto:
        file = await context.bot.get_file(foto[-1].file_id)  # la de mayor resolución
        data = bytes(await file.download_as_bytearray())
        await _agregar_imagen(buf, "image/jpeg", data)
    elif documento:
        file = await context.bot.get_file(documento.file_id)
        data = bytes(await file.download_as_bytearray())
        mime = (documento.mime_type or "").lower()
        if mime == "application/pdf":
            buf["pdfs"].append(data)
        elif mime.startswith("image/"):
            if mime == "image/jpg":
                mime = "image/jpeg"  # alias común
            if mime in _FORMATOS_IMAGEN_ACEPTADOS:
                await _agregar_imagen(buf, mime, data)
            else:
                # La API de Claude solo acepta JPEG/PNG/GIF/WebP; convertimos con Pillow.
                try:
                    from PIL import Image
                    img = Image.open(BytesIO(data))
                    img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
                    out = BytesIO()
                    img.save(out, format="PNG", optimize=True)
                    await _agregar_imagen(buf, "image/png", out.getvalue())
                except Exception:
                    await msg.reply_text(
                        f"No puedo procesar imágenes en formato {mime}. "
                        f"Mándalas como foto (no como archivo), o conviértelas a JPG/PNG."
                    )
                    return
        else:
            await msg.reply_text("Ese tipo de archivo no lo puedo leer. Mándame imágenes o PDF.")
            return

    # --- Si vino con pie de foto, ese es el requerimiento ---
    if msg.caption:
        await _procesar(update, context, session_id, uid, user, msg.caption)
        return

    if texto:
        await _procesar(update, context, session_id, uid, user, texto)
        return

    if not (foto or documento):
        await msg.reply_text("❌ Formato de mensaje no soportado.")
        return

    # Adjunto sin caption ni texto: si ya veníamos conversando, solo confirmamos.
    est = cuestionario.estado_de(uid)
    n = len(buf["imagenes"]) + len(buf["pdfs"])
    if est.texto_acumulado.strip():
        await msg.reply_text(f"📎 Recibí ({n} adjunto(s) en total).")
    else:
        await _procesar(update, context, session_id, uid, user, "")


async def _procesar(update: Update, context: ContextTypes.DEFAULT_TYPE,
                     session_id: str, uid: int, user, descripcion: str):
    buf = _buf(session_id)
    n_imgs, n_pdfs_in = len(buf["imagenes"]), len(buf["pdfs"])

    if cuestionario.es_comando_cancelar(descripcion):
        cuestionario.limpiar(uid)
        BUFFERS.pop(session_id, None)
        await update.message.reply_text(
            "❎ Cuestionario cancelado. Cuando quieras empezar de nuevo, mándame los datos del proyecto."
        )
        return

    hay_archivos = (n_imgs + n_pdfs_in) > 0
    decision = cuestionario.procesar(uid, descripcion, hay_archivos)

    if decision.accion == "esperar":
        return  # sin nada que generar todavía, no respondemos
    if decision.accion == "preguntar":
        # Faltan datos: preguntamos y NO llamamos a Claude. Los adjuntos
        # quedan en el buffer para cuando el usuario complete la info.
        await update.message.reply_text(decision.mensaje, parse_mode="Markdown")
        return

    # accion == "generar": ya tenemos todo lo necesario.
    descripcion_completa = decision.texto_completo
    if buf["capciones"]:
        capciones_texto = "\n".join(f"- Imagen {i+1}: {c}" for i, c in enumerate(buf["capciones"]))
        descripcion_completa += (
            "\n\n[Descripción automática de las imágenes recibidas, generada por otro "
            f"modelo más rápido — úsala como orientación, no como fuente exacta de medidas]\n{capciones_texto}"
        )

    status = await update.message.reply_text("🛠️ Procesando… (puede tardar 1–2 min)")
    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)

    resultado = await generar_proyecto_pm(
        descripcion=descripcion_completa,
        imagenes=buf["imagenes"],
        pdfs=buf["pdfs"],
        session_id=session_id,
        tg_user_id=uid,
        tg_username=user.username,
        tg_full_name=user.full_name,
    )
    BUFFERS.pop(session_id, None)  # limpiamos el buffer pase lo que pase

    if resultado.error:
        await status.edit_text(f"❌ Error al generar: {resultado.error}")
        return

    for parte in resultado.partes_texto:
        await update.message.reply_text(parte)

    if resultado.validacion_texto:
        for parte in resultado.validacion_texto:
            await update.message.reply_text(parte)

    if resultado.proyecto:
        if resultado.link_visor_3d:
            await update.message.reply_text(
                f"🌐 <a href=\"{resultado.link_visor_3d}\"><b>VER MODELO 3D EN TU VISOR</b></a>",
                parse_mode="HTML", disable_web_page_preview=True,
            )

        await status.edit_text("🧱 Enviando planos y renders…")
        for p in resultado.archivos:
            try:
                if p.suffix.lower() == ".png":
                    await update.message.reply_photo(photo=p.open("rb"))
                else:
                    await update.message.reply_document(document=p.open("rb"), filename=p.name)
            except Exception as e:  # noqa: BLE001
                log.warning("No se pudo enviar %s: %s", p, e)
        if not resultado.archivos and not resultado.link_visor_3d:
            await update.message.reply_text(
                "⚠️ No pude generar planos/renders (¿faltan dependencias en el servidor?). "
                "El diseño y la cotización de arriba siguen siendo válidos."
            )

    try:
        await status.delete()
    except Exception:  # noqa: BLE001
        pass

    limpiar_temporales(resultado)
