"""trimesh (venv actual) no trae decodificador de KHR_draco_mesh_compression
en modo LECTURA -- solo lo soporta para exportar. Todos los .glb reales del
catalogo (bucket 'modelos' de Supabase) estan comprimidos con Draco (ver
comentario de EXT_texture_webp/KHR_draco_mesh_compression en index.html
sobre el mismo problema en el visor Three.js), asi que sin este parche
trimesh.load() carga la escena "bien" en apariencia (mismo numero de
vertices/caras) pero con TODOS los vertices colapsados en un solo punto --
el placeholder de ceros que arma internamente cuando un accessor no trae
bufferView propio (que es justo el caso normal para atributos comprimidos
con Draco).

Importar este modulo UNA VEZ antes de llamar a trimesh.load(...) en
cualquier .glb comprimido es suficiente -- registra el handler globalmente
en el registro de extensiones de trimesh.
"""
import numpy as np
import DracoPy
from trimesh.exchange.gltf.extensions import register_handler


def _reemplazar(accessors: list, accessor_idx: int, array) -> None:
    """Sustituye el array placeholder (relleno de ceros) por los datos
    reales ya decodificados, preservando el dtype/shape que trimesh ya
    infirio del accessor original (count, componentType, type)."""
    placeholder = accessors[accessor_idx]
    accessors[accessor_idx] = (
        np.asarray(array).reshape(placeholder.shape).astype(placeholder.dtype)
    )


@register_handler("KHR_draco_mesh_compression", scope="primitive_preprocess")
def _decodificar_draco(context: dict):
    data = context["data"]
    primitive = context["primitive"]
    accessors = context["accessors"]  # ya son arrays numpy resueltos por trimesh
    views = context["views"]

    comprimido = bytes(views[data["bufferView"]])
    malla = DracoPy.decode(comprimido)

    atributos = primitive.get("attributes", {})
    if "POSITION" in atributos:
        _reemplazar(accessors, atributos["POSITION"], malla.points)
    if "NORMAL" in atributos and getattr(malla, "normals", None) is not None and len(malla.normals):
        _reemplazar(accessors, atributos["NORMAL"], malla.normals)
    if "TEXCOORD_0" in atributos and getattr(malla, "tex_coord", None) is not None and len(malla.tex_coord):
        _reemplazar(accessors, atributos["TEXCOORD_0"], malla.tex_coord)

    if "indices" in primitive:
        _reemplazar(accessors, primitive["indices"], malla.faces.flatten())

    return None
