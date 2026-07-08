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