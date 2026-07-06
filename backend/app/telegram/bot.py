"""
Construcción y ciclo de vida de la aplicación de Telegram (python-telegram-bot).
El lifespan de FastAPI (en app/main.py) usa `iniciar_bot` / `detener_bot`.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from telegram.request import HTTPXRequest
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from ..config import BOT_TOKEN
from .handlers import start_command, cancelar_command, manejar_mensaje_telegram


def construir_telegram_app() -> Application:
    t_request = HTTPXRequest(connect_timeout=15.0, read_timeout=15.0)
    tg_app = Application.builder().token(BOT_TOKEN).request(t_request).build()

    tg_app.add_handler(CommandHandler("start", start_command))
    tg_app.add_handler(CommandHandler("cancelar", cancelar_command))

    filtro_total = filters.Document.ALL | filters.PHOTO | filters.TEXT | filters.VOICE
    tg_app.add_handler(MessageHandler(filtro_total, manejar_mensaje_telegram))
    return tg_app


@asynccontextmanager
async def lifespan(app: FastAPI):
    tg_app = construir_telegram_app()

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
