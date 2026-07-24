def catalogo_to_document(item):

    reglas = item.get("reglas") or ""

    return f"""
DOCUMENTO DEL CATÁLOGO INDUSTRIAL

Código:
{item["codigo"]}

Descripción:
{item["descripcion"]}

Familia:
{item["familia"]}

Categoría:
{item["categoria"]}

Frente:
{item["frente_mm"]} mm

Fondo:
{item["fondo_mm"]} mm

Altura:
{item["altura_mm"]} mm

Peralte:
{item["peralte_mm"]}

Calibre:
{item["calibre"]}

Capacidad:
{item["carga_kg"]} kg

Escalonado:
{item["escalon"]}

Precio:
{item["precio"]}

Reglas técnicas:
{reglas}

Este componente pertenece al catálogo oficial de RackMind.
"""


def correccion_to_document(item):
    """
    Arma el texto que se vectoriza para cada corrección — necesita traer
    tanto el comentario del cliente como el 'antes/después' para que una
    búsqueda semántica futura encuentre correcciones parecidas por lo que
    el cliente PIDIÓ, no solo por el tipo de rack.
    """
    origen = item.get("origen") or "manual"
    tipo = item.get("tipo_rack") or "todos"
    pieza = item.get("pieza_afectada") or "—"
    veces = item.get("veces_repetida") or 1

    return f"""
CORRECCIÓN REGISTRADA ({origen})

Tipo de rack:
{tipo}

Pieza afectada:
{pieza}

Comentario / error detectado:
{item["descripcion_error"]}

Instrucción correctiva:
{item["instruccion_correctiva"]}

Veces que se ha repetido este mismo caso:
{veces}

Clave del proyecto relacionado:
{item.get("proyecto_clave") or "—"}
"""


def chunk_texto(texto: str, chunk_size: int = 1000, overlap: int = 150) -> list[str]:
    """Parte un documento largo en ventanas con solape (fichas técnicas)."""
    texto = (texto or "").strip()
    if not texto:
        return []
    if len(texto) <= chunk_size:
        return [texto]

    chunks: list[str] = []
    paso = max(chunk_size - overlap, 1)
    inicio = 0
    while inicio < len(texto):
        fin = min(inicio + chunk_size, len(texto))
        trozo = texto[inicio:fin].strip()
        if trozo:
            chunks.append(trozo)
        if fin >= len(texto):
            break
        inicio += paso
    return chunks


def manual_to_document(nombre: str, fragmento: str, indice: int, total: int) -> str:
    """Texto indexable de un fragmento de ficha técnica local."""
    return f"""
FICHA TÉCNICA / MANUAL

Archivo:
{nombre}

Fragmento:
{indice + 1} de {total}

Contenido:
{fragmento}
""".strip()
