"""Endpoints del catálogo de piezas: subir modelo 3D, listar y eliminar."""
import os
import urllib.parse
import tempfile
import subprocess
from fastapi import APIRouter, Form, File, UploadFile, HTTPException

from ..clients import supabase, supabase_service
from ..config import BACKEND_DIR
from ..services.storage_service import _build_public_url

router = APIRouter(prefix="/catalogo", tags=["catalogo"])


@router.post("/upload-modelo")
async def upload_modelo_catalogo(
    codigo_sku: str = Form(...),
    nombre: str = Form(...),
    tipo: str = Form(...),
    peso_maximo_soportado_kg: float = Form(...),
    longitud_metros: float = Form(...),
    altura_metros: float = Form(...),
    profundidad_metros: float = Form(...),
    file: UploadFile = File(...),
    comprimir_draco: bool = Form(True),
    encoder_method: str = Form("edgebreaker"),
):
    """
    Sube un modelo .glb/.gltf, lo comprime opcionalmente con Draco,
    lo guarda en Supabase Storage (bucket 'modelos') y registra/actualiza
    la pieza en la tabla catalogo_piezas con la URL del modelo.
    """
    import tempfile, os

    service_client = supabase_service if supabase_service else supabase
    original_bytes = await file.read()
    filename = file.filename or f"{codigo_sku}.glb"
    storage_path = f"catalogo/{codigo_sku}/{filename}"

    final_bytes = original_bytes
    original_size = len(original_bytes)
    compressed_size = original_size

    # 1) Comprimir con Draco si se solicita
    if comprimir_draco:
        cli_js = os.path.join(BACKEND_DIR, 'node_modules', '@gltf-transform', 'cli', 'bin', 'cli.js')
        if not os.path.exists(cli_js):
            raise HTTPException(status_code=500, detail="gltf-transform no instalado. Ejecuta `npm install` en backend/.")

        with tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as tmp_in,              tempfile.NamedTemporaryFile(suffix=".glb", delete=False) as tmp_out:
            tmp_in.write(original_bytes)
            tmp_in.flush()
            tmp_in_name = tmp_in.name
            tmp_out_name = tmp_out.name

        try:
            cmd = ['node', cli_js, 'draco', tmp_in_name, tmp_out_name, '--method', encoder_method]
            proc = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=180)
            with open(tmp_out_name, 'rb') as f:
                final_bytes = f.read()
            compressed_size = len(final_bytes)
            # Renombrar para indicar que está comprimido
            if not filename.endswith('.draco.glb'):
                storage_path = f"catalogo/{codigo_sku}/{filename.replace('.glb', '.draco.glb').replace('.gltf', '.draco.glb')}"
        except subprocess.CalledProcessError as cpe:
            error_detail = cpe.stderr or cpe.stdout or f"Código de salida: {cpe.returncode}"
            raise HTTPException(status_code=500, detail=f"Compresión fallida: {error_detail}") from cpe
        finally:
            for f in [tmp_in_name, tmp_out_name]:
                try: os.unlink(f)
                except: pass

    # 2) Subir a Supabase Storage
    try:
        service_client.storage.from_("modelos").upload(
            path=storage_path,
            file=final_bytes,
            file_options={"cache-control": "3600", "upsert": "true"}
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error subiendo a Storage: {exc}") from exc

    # 3) Construir URL pública
    url_modelo_glb = _build_public_url("modelos", storage_path)

    # 4) Upsert en catalogo_piezas
    try:
        supabase.table("catalogo_piezas").upsert({
            "codigo_sku": codigo_sku,
            "nombre": nombre,
            "tipo": tipo,
            "peso_maximo_soportado_kg": peso_maximo_soportado_kg,
            "longitud_metros": longitud_metros,
            "altura_metros": altura_metros,
            "profundidad_metros": profundidad_metros,
            "url_modelo_glb": url_modelo_glb,
        }, on_conflict="codigo_sku").execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error registrando en catálogo: {exc}") from exc

    reduction = round((original_size - compressed_size) / original_size * 100, 1) if original_size > 0 else 0

    return {
        "status": "success",
        "codigo_sku": codigo_sku,
        "storage_path": storage_path,
        "url_modelo_glb": url_modelo_glb,
        "original_size": original_size,
        "final_size": compressed_size,
        "reduction_percent": reduction,
        "draco_applied": comprimir_draco,
    }


@router.get("/piezas")
def listar_catalogo():
    """Lista todas las piezas del catálogo con su URL de modelo 3D."""
    try:
        result = supabase.table("catalogo_piezas").select("*").order("created_at", desc=True).execute()
        return {"piezas": result.data or []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/piezas/{codigo_sku}")
async def eliminar_pieza_catalogo(codigo_sku: str):
    """
    Elimina atómicamente:
    1. El archivo .glb del bucket 'modelos' (ruta catalogo/{sku}/)
    2. El registro en catalogo_piezas
    """
    service_client = supabase_service if supabase_service else supabase
    errors = []

    # 1) Obtener URL del modelo para extraer la ruta en Storage
    try:
        result = supabase.table("catalogo_piezas").select("url_modelo_glb").eq("codigo_sku", codigo_sku).single().execute()
        url_modelo = (result.data or {}).get("url_modelo_glb", "")
        if url_modelo and "/storage/v1/object/public/modelos/" in url_modelo:
            relative_path = url_modelo.split("/storage/v1/object/public/modelos/", 1)[1]
            relative_path = urllib.parse.unquote(relative_path)
            try:
                service_client.storage.from_("modelos").remove([relative_path])
            except Exception as e:
                errors.append(f"Storage: {e}")
    except Exception as e:
        errors.append(f"Lookup: {e}")

    # 2) Eliminar registro de la tabla (siempre, aunque falle el storage)
    try:
        supabase.table("catalogo_piezas").delete().eq("codigo_sku", codigo_sku).execute()
    except Exception as e:
        errors.append(f"DB: {e}")
        raise HTTPException(status_code=500, detail=f"Error eliminando de BD: {e}")

    if errors:
        return {"status": "partial", "codigo_sku": codigo_sku,
                "message": "Registro eliminado pero hubo errores en Storage.", "errors": errors}
    return {"status": "success", "codigo_sku": codigo_sku}
