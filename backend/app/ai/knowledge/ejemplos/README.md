# Ejemplos dorados (disco / git — NO Supabase)

Todo archivo **`.json`** en esta carpeta es un caso dorado para:

1. Formato del proyectista (1–2 se embeben en el system prompt).
2. Evaluación medible: `python -m app.engineering.evaluacion` y pytest.

**No se indexan en RAG / Supabase.** Solo `knowledge/tecnico/*` va a
`knowledge_chunks` como `tipo=manual`.

## Convención de nombres

| Prefijo / nombre | Tipo de rack |
|---|---|
| `ejemplo_proyecto_*`, `ejemplo_selectivo_*` | Selectivo (pesada/ligera) |
| `ejemplo_cantilever_*` | Cantiléver |
| `ejemplo_entrepiso_*` | Entrepiso / mezzanine |

## Formato requerido (rejilla simple)

- `layout` con `modulos_x`, `modulos_y`, `frente_mm`, `fondo_mm`, `pasillo_mm`,
  `niveles` (empieza en 0), `altura_total_mm`, `peralte_larguero_mm`.
- **NO** `zones` ni `background_image`.
- `materiales` con `pzas`, `codigo`, `descripcion`, `color`, `obs`, `precio`.
- `memoria` y `observaciones` con detalle de ingeniería.

## Cómo agregar uno

1. Copia un JSON de esta carpeta del mismo tipo.
2. Ajusta layout / despiece / memoria.
3. Corre: `cd backend && python -m app.engineering.evaluacion`
4. Corre: `pytest tests/test_casos_dorados.py -q`

Tras editar, reinicia el bot si quieres que los dorados del prompt se recarguen.
