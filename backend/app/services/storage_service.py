"""
Funciones auxiliares de Supabase Storage: resolución de nombres de bucket/carpeta
(por variantes de espacios/guiones), URLs públicas, y listados de archivos/carpetas.
No expone endpoints — eso vive en app/routers/storage.py.
"""
import os
import urllib.parse
import urllib.request
from ..clients import supabase, supabase_service


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
            mimetype = "model/gltf-binary"
            # storage_client.info() falla silenciosamente en muchas versiones del SDK.
            # Se hace HEAD a la URL pública para obtener Content-Length real.
            try:
                import urllib.request as _req
                head_req = _req.Request(url, method="HEAD")
                with _req.urlopen(head_req, timeout=5) as resp:
                    size = int(resp.headers.get("Content-Length") or 0)
                    mimetype = resp.headers.get("Content-Type") or mimetype
            except Exception:
                # Fallback: intentar info() del SDK
                try:
                    info = storage_client.info(relative_path)
                    if isinstance(info, dict):
                        size = int(info.get("size") or info.get("metadata", {}).get("size") or 0)
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


def _item_a_dict(item) -> dict | None:
    """
    Normaliza un ítem de storage.list() a dict plano, sin importar si el SDK
    lo devolvió como dict (lo usual) o como un objeto con atributos (algunas
    versiones de storage3/supabase-py lo hacen así).
    """
    if isinstance(item, dict):
        return item
    if hasattr(item, "__dict__"):
        return {k: v for k, v in vars(item).items() if not k.startswith("_")}
    if hasattr(item, "model_dump"):
        try:
            return item.model_dump()
        except Exception:
            return None
    return None


def _listar_entradas_storage(bucket: str, folder: str = "") -> dict:
    """
    Lista el contenido de un bucket/carpeta distinguiendo subcarpetas de
    archivos reales (Supabase Storage no tiene carpetas de verdad: los
    ítems que Supabase devuelve sin 'id' son prefijos/carpetas).
    Usado por el explorador de 'Alimentar IA' (buckets 'cotizaciones' y
    'precios unitarios').

    Prueba TODAS las variantes de nombre de bucket y solo se queda con el
    primer resultado que realmente traiga carpetas o archivos; si un
    candidato responde vacío (por ejemplo por un nombre de bucket que no
    coincide exactamente), sigue probando en vez de devolver vacío de una vez.
    """
    folder_clean = (folder or "").strip().strip("/")
    mejor_resultado = None

    for candidate_bucket in _candidate_bucket_names(bucket):
        try:
            payload = _get_storage_client().from_(candidate_bucket).list(
                folder_clean,
                {"limit": 1000, "offset": 0, "sortBy": {"column": "name", "order": "asc"}},
            )
            payload = _normalize_storage_payload(payload)
            print(f"[storage/entradas] bucket={candidate_bucket!r} folder={folder_clean!r} -> {len(payload) if isinstance(payload, list) else 'no-list'} ítems crudos")

            if not isinstance(payload, list):
                continue

            carpetas, archivos = [], []
            for raw_item in payload:
                item = _item_a_dict(raw_item)
                if item is None:
                    print(f"[storage/entradas] ítem no reconocible, se ignora: {raw_item!r}")
                    continue

                name = item.get("name")
                if not name or name in (".emptyFolderPlaceholder", ".keep"):
                    continue

                relative_path = f"{folder_clean}/{name}" if folder_clean else name

                # Supabase devuelve las subcarpetas sin 'id' (son solo prefijos, no objetos reales).
                if item.get("id") is None:
                    carpetas.append({"name": name, "path": relative_path})
                else:
                    size, content_type = _normalize_storage_item(item)
                    archivos.append({
                        "name": name,
                        "path": relative_path,
                        "size": size,
                        "type": content_type,
                        "url": _build_public_url(candidate_bucket, relative_path),
                    })

            resultado = {"bucket": candidate_bucket, "folder": folder_clean, "carpetas": carpetas, "archivos": archivos}

            if carpetas or archivos:
                return resultado

            # Nos quedamos con el primer resultado "válido pero vacío" por si
            # ningún candidato trae contenido; mejor devolver una respuesta
            # limpia con el bucket correcto que un error genérico.
            if mejor_resultado is None:
                mejor_resultado = resultado
        except Exception as e:
            print(f"[storage/entradas] error probando bucket={candidate_bucket!r} folder={folder_clean!r}: {e}")
            continue

    return mejor_resultado or {"bucket": bucket, "folder": folder_clean, "carpetas": [], "archivos": []}
