"""Extracción de texto: PDF, imágenes (OCR) y transcripción de audio."""
import base64
import logging
import os
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image
from ..clients import ocr_reader, groq_client

log = logging.getLogger("ocr_service")


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


def comprimir_imagen(data: bytes, max_lado_px: int = 1568, calidad_jpeg: int = 82) -> tuple[str, bytes]:
    """
    Reescala/recomprime una imagen antes de mandarla a Claude. Las fotos de
    celular suelen venir en 3000-4000px por lado; Claude cobra tokens según
    los píxeles de la imagen, así que bajarla a 1568px (el máximo útil que
    Anthropic recomienda — de ahí para arriba no mejora la lectura, solo
    cobra más) reduce el costo por imagen sin perder legibilidad.

    Devuelve (media_type, bytes) — siempre JPEG, para un tamaño consistente
    y menor que PNG en fotos.
    """
    try:
        img = Image.open(BytesIO(data))
        img = img.convert("RGB")
        ancho, alto = img.size
        lado_mayor = max(ancho, alto)
        if lado_mayor > max_lado_px:
            escala = max_lado_px / lado_mayor
            img = img.resize((int(ancho * escala), int(alto * escala)), Image.LANCZOS)
        out = BytesIO()
        img.save(out, format="JPEG", quality=calidad_jpeg, optimize=True)
        return "image/jpeg", out.getvalue()
    except Exception as e:  # noqa: BLE001 — si falla la compresión, se manda la imagen original
        log.warning("No se pudo comprimir la imagen, se manda tal cual: %s", e)
        return "image/jpeg", data


def describir_imagen_groq(image_bytes: bytes, media_type: str = "image/jpeg") -> str:
    """
    Genera una descripción corta (1-3 líneas) de una imagen usando la visión
    de Groq — rápida y barata — ANTES de mandarla a Claude. Esa descripción
    se agrega como texto al mensaje, para que Claude llegue con contexto ya
    resuelto y gaste menos tokens de "pensamiento" reconociendo cada imagen
    desde cero.

    ⚠️ El modelo de visión de Groq cambia de nombre/disponibilidad seguido
    (p. ej. llama-4-scout se deprecó en junio 2026). Si esto empieza a fallar
    con "model not found", revisa el modelo vigente en
    https://console.groq.com/docs/vision y actualiza MODELO_VISION_GROQ.
    """
    MODELO_VISION_GROQ = "qwen/qwen3.6-27b"
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    try:
        completion = groq_client.chat.completions.create(
            model=MODELO_VISION_GROQ,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": (
                        "Describe brevemente (máximo 3 líneas, en español) qué se ve en esta "
                        "imagen en el contexto de una requisición de racks industriales: "
                        "tipo de espacio, medidas visibles, columnas, tarimas, montacargas, "
                        "si es boceto/plano/foto del sitio, etc. Responde solo la descripción, "
                        "sin preámbulo ni relleno."
                    )},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
                ],
            }],
            temperature=0.2,
            max_completion_tokens=150,
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception as e:  # noqa: BLE001 — es una ayuda opcional, nunca debe romper el flujo
        log.warning("describir_imagen_groq falló (modelo vigente puede haber cambiado): %s", e)
        return ""
