"""Consultas al catálogo de piezas reales disponibles en Supabase (con modelos .glb)."""
from ..clients import supabase


def consultar_catalogo_piezas() -> list:
    """
    Trae el inventario de componentes reales disponibles de Supabase
    (tabla catalogo_piezas — codigo_sku, tipo, url_modelo_glb...).
    Si la tabla está vacía, no existe, o la consulta falla, provee el catálogo
    técnico con los modelos de precisión reales que ya tienes en Supabase.
    """
    fallback_piezas = [
        {"sku": "(-)_RACK_180X61X151", "nombre": "Rack Estructural Base 1.80m x 0.61m",
         "tipo": "rack_base", "peso_maximo_soportado_kg": 1500,
         "longitud_metros": 1.80, "altura_metros": 1.51, "profundidad_metros": 0.61},
        {"sku": "CABECERA_302X91_CON_TRAVESANO", "nombre": "Cabecera Lateral 3.02m con Travesaño",
         "tipo": "marco", "peso_maximo_soportado_kg": 2200,
         "longitud_metros": 0.08, "altura_metros": 3.02, "profundidad_metros": 0.91},
        {"sku": "MENSULA_GOTA_CARGA_LIGERA_DERECHA", "nombre": "Ménsula Gota Carga Ligera Derecha",
         "tipo": "mensula", "peso_maximo_soportado_kg": 800,
         "longitud_metros": 0.30, "altura_metros": 0.10, "profundidad_metros": 0.10},
    ]
    try:
        resultado = supabase.table("catalogo_piezas").select("*").execute()
        if resultado.data and len(resultado.data) > 0:
            return resultado.data
        return fallback_piezas
    except Exception:
        return fallback_piezas
