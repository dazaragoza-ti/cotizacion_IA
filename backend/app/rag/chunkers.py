from typing import Dict


def catalogo_to_document(item: Dict) -> str:

    return f"""
TIPO: CATALOGO

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

Precio:

{item["precio"]}

Reglas:

{item["reglas"]}
"""