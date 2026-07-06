"""Endpoints de exploración, subida y optimización de Supabase Storage."""
import os
import asyncio
import urllib.request
import tempfile
import subprocess
from fastapi import APIRouter, Form, File, UploadFile, HTTPException

from ..clients import supabase, supabase_service
from ..config import BACKEND_DIR
from ..services.storage_service import (
    _listar_archivos_storage, _listar_entradas_storage,
    _candidate_bucket_names, _get_storage_client, _build_public_url,
)
from ..services.ocr_service import extraer_texto_pdf, extraer_texto_imagen

router = APIRouter(prefix="/storage", tags=["storage"])


@router.get("/files")
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


@router.get("/entradas")
def listar_entradas_storage(bucket: str = "cotizaciones", folder: str = ""):
    """Explorador de carpetas: devuelve carpetas y archivos por separado para un bucket/carpeta dados."""
    try:
        return _listar_entradas_storage(bucket, folder)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/carpeta")
async def crear_carpeta_storage(bucket: str = Form(...), folder_path: str = Form(...)):
    """
    Crea una subcarpeta dentro de un bucket. Como Supabase Storage no tiene
    carpetas reales (solo prefijos de ruta), se simula subiendo un archivo
    placeholder invisible '.keep' dentro de la ruta deseada.
    """
    folder_clean = folder_path.strip().strip("/")
    if not folder_clean:
        raise HTTPException(status_code=400, detail="El nombre de la carpeta no puede estar vacío.")

    placeholder_path = f"{folder_clean}/.keep"
    ultimo_error = None
    for candidate_bucket in _candidate_bucket_names(bucket):
        try:
            _get_storage_client().from_(candidate_bucket).upload(
                path=placeholder_path,
                file=b"",
                file_options={"cache-control": "3600", "upsert": "true", "content-type": "text/plain"},
            )
            return {"status": "success", "bucket": candidate_bucket, "folder": folder_clean}
        except Exception as e:
            ultimo_error = e
            continue

    raise HTTPException(status_code=500, detail=f"No se pudo crear la carpeta: {ultimo_error}")


@router.post("/subir-archivo")
async def subir_archivo_storage(
    bucket: str = Form(...),
    folder: str = Form(""),
    file: UploadFile = File(...),
):
    """
    Sube un archivo a cualquier bucket/carpeta. A diferencia de /storage/upload
    (que está fijo al bucket 'modelos' y hace OCR para entrenar a la IA), este
    endpoint es genérico: lo usa el explorador de carpetas de 'Alimentar IA'
    para subir directamente a 'cotizaciones' o 'precios unitarios'.
    """
    folder_clean = (folder or "").strip().strip("/")
    contents = await file.read()
    nombre_sanitizado = f"{int(asyncio.get_event_loop().time())}_{file.filename}"
    path_storage = f"{folder_clean}/{nombre_sanitizado}" if folder_clean else nombre_sanitizado

    ultimo_error = None
    for candidate_bucket in _candidate_bucket_names(bucket):
        try:
            _get_storage_client().from_(candidate_bucket).upload(
                path=path_storage,
                file=contents,
                file_options={"cache-control": "3600", "upsert": "true"},
            )
            return {
                "status": "success",
                "bucket": candidate_bucket,
                "path": path_storage,
                "url": _build_public_url(candidate_bucket, path_storage),
            }
        except Exception as e:
            ultimo_error = e
            continue

    raise HTTPException(status_code=500, detail=f"No se pudo subir el archivo: {ultimo_error}")


@router.post("/files/replace")
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


@router.post("/files/optimize")
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

            # 3) Ejecutar gltf-transform via el JS entry point directamente con node
            # Esto evita el problema de que en Windows el .cmd no es ejecutable por node,
            # y en Linux el shebang puede no tener permisos de ejecucion.
            # Se llama siempre como: node <ruta_al_js> draco input output --method X
            cli_js = os.path.join(BACKEND_DIR, 'node_modules', '@gltf-transform', 'cli', 'bin', 'cli.js')
            if not os.path.exists(cli_js):
                raise HTTPException(
                    status_code=500,
                    detail="No se encontró @gltf-transform/cli. Ejecuta `npm install` en la carpeta backend/."
                )

            cmd = ['node', cli_js, 'draco', tmp_in.name, tmp_out.name, '--method', encoder_method]
            try:
                print(f"[optimize] running command: {cmd}")
                proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
                print(f"[optimize] stdout: {proc.stdout}")
            except subprocess.CalledProcessError as cpe:
                # gltf-transform v4 escribe errores tanto a stdout como a stderr
                error_detail = cpe.stderr or cpe.stdout or f"Codigo de salida: {cpe.returncode}"
                print(f"[optimize] CalledProcessError stdout={cpe.stdout!r} stderr={cpe.stderr!r}")
                raise HTTPException(status_code=500, detail=f"Compresion fallida: {error_detail}") from cpe
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


@router.post("/upload")
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


@router.delete("/files/{filename}")
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
