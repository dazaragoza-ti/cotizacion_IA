# Guía de testing: verificar el aprendizaje continuo end-to-end

Esta guía sirve para comprobar, con pasos concretos, que el sistema realmente
aprende de sus correcciones a lo largo del tiempo (no solo que el código
existe, sino que el ciclo completo se ve reflejado en Supabase y en la UI).

El ciclo completo es:

```
Corrección vía Telegram → correcciones_armado (veces_repetida++)
        → knowledge_stats (contadores por SKU)
        → knowledge_edges (grafo de relaciones, vía RPC reforzar_relacion)
        → PromotionEngine (nueva → importante → candidata → permanente)
        → reglas_armado (cuando llega a "permanente")
        → Context Builder inyecta las relaciones aprendidas en el prompt
          de Claude para el SIGUIENTE proyecto
```

Cada sección de abajo prueba un eslabón de esta cadena.

---

## 1. Corrección manual vía Telegram → `correcciones_armado`

**Cómo disparar una corrección:** el bot detecta una corrección comparando
la `clave` del proyecto nuevo contra el último proyecto de la misma sesión
de Telegram (`correcciones_pm_service.es_correccion()`). No hay un comando
explícito — basta con responder en el mismo chat, sobre el mismo proyecto,
señalando el error (por ejemplo: "la ménsula que pusiste no es la correcta,
usa la LRS7360 en vez de la LRS7355").

**Pasos:**
1. Genera un proyecto por Telegram (descripción con los 4 datos críticos).
2. En el mismo chat, manda un mensaje de corrección sobre ESE proyecto
   (misma `clave`).
3. En Supabase, revisa la tabla `correcciones_armado`:
   ```sql
   select proyecto_clave, descripcion_error, veces_repetida, origen, created_at
   from correcciones_armado
   order by created_at desc limit 5;
   ```
4. **Verificación:** debe aparecer una fila nueva con `origen = 'manual'`.
   Si repites la MISMA corrección (mismo `proyecto_clave` +
   `descripcion_error`) en otro proyecto, `veces_repetida` debe
   incrementarse en vez de crear una fila duplicada.

---

## 2. `knowledge_stats` y `knowledge_edges` (el grafo de aprendizaje)

Cuando se registra una corrección, `correction_processor._aprender()`
(`backend/app/engineering/correction_processor.py`) hace dos cosas:

- `metrics.increment_many(...)` incrementa contadores en `knowledge_stats`
  (veces que un SKU fue usado/reemplazado/rechazado/recomendado).
- `_reforzar_relacion()` llama al RPC atómico `reforzar_relacion` (Postgres,
  migración `0003_reforzar_relacion_rpc.sql`), que incrementa `ocurrencias` y
  recalcula `confidence`/`validada` en `knowledge_edges` en una sola
  sentencia (evita condiciones de carrera si dos correcciones llegan casi
  al mismo tiempo).

**Pasos:**
1. Después de una corrección que mencione un SKU reemplazado (por ejemplo
   "usa LRS7360 en vez de LRS7355"), revisa:
   ```sql
   select sku, veces_usado, veces_reemplazado, veces_rechazado, veces_recomendado
   from knowledge_stats where sku in ('LRS7355', 'LRS7360');

   select origen, relacion, destino, ocurrencias, confidence, validada
   from knowledge_edges
   where origen = 'LRS7355' or destino = 'LRS7360'
   order by updated_at desc;
   ```
2. **Verificación:** `ocurrencias` debe subir en 1 cada vez que se repite el
   mismo patrón de corrección; `confidence` sube con `ocurrencias` (umbral
   interno `UMBRAL_CONFIDENCE = 30`, equivalente a `confidence` cerca de 0.95).
3. Repite la misma corrección unas 5 veces (con proyectos distintos, para
   que cuente como repetición real) y confirma que `ocurrencias` sube cada
   vez — es la prueba de que el refuerzo es acumulativo y no se resetea.

---

## 3. PromotionEngine: de "nueva" a regla permanente

`backend/app/engineering/promotion.py` clasifica cada relación por su
contador de `ocurrencias` (función `estado_de()`):

| Estado | Umbral de `ocurrencias` |
|---|---|
| `nueva` | menor a 5 |
| `importante` | 5 o más |
| `candidata` | 20 o más |
| `permanente` | 50 o más |

Al llegar a `permanente`, `_materializar()` inserta (de forma idempotente)
una fila en `reglas_armado`.

**Pasos:**
1. Sigue reforzando la misma relación (repite la corrección) hasta que
   `knowledge_edges.ocurrencias` cruce 5, luego 20, luego 50.
2. En la pantalla Estadísticas de Flutter (ver sección 4), el panel
   "Correcciones aprendidas" debe reflejar el cambio de etiqueta según
   `veces_repetida`: nueva, luego importante, luego candidata, luego
   permanente.
3. Cuando cruce 50, verifica en Supabase:
   ```sql
   select condicion, descripcion, created_at from reglas_armado
   order by created_at desc limit 5;
   ```
4. **Verificación:** debe aparecer una fila nueva con
   `condicion` en el formato `<relacion>:codigo=<origen>->to=<destino>`.
   Si repites el proceso para la MISMA relación ya materializada, no debe
   duplicarse (la inserción busca primero por `condicion`).

---

## 4. Pantalla de Estadísticas ("Aprendizaje continuo") en Flutter

Ruta: `frontend/rackbuilder_dashboard/lib/features/estadisticas/` — no es
una URL, es un módulo del dashboard de una sola página (selecciona
"Aprendizaje continuo" en el menú lateral).

**Pasos:**
1. Abre el dashboard Flutter, entra al módulo "Aprendizaje continuo".
2. Verifica que el ranking de SKUs (consume `GET /stats/top`) coincide con
   lo que ves directamente en `knowledge_stats` (paso 2).
3. Verifica que el panel "Correcciones aprendidas" (consume `GET
   /correcciones`) muestra la corrección que registraste en el paso 1, con
   la barra de progreso y el estado (nueva/importante/candidata/permanente)
   coincidiendo con `veces_repetida`.

---

## 5. Context Builder: ¿el aprendizaje afecta al SIGUIENTE proyecto?

Esta es la prueba más importante: confirmar que lo aprendido no se queda
solo en Supabase, sino que cambia el comportamiento futuro de Claude.

`context_builder._bloque_relaciones_grafo()` inyecta al prompt las
relaciones con `confidence >= 0.5` para los SKUs del proyecto anterior, con
este formato exacto:

```
[Relaciones aprendidas del historial de correcciones (Knowledge Graph) - patrones reales detectados entre piezas de este proyecto; considéralos con la misma prioridad que las correcciones aprendidas de abajo]
- LRS7355 reemplaza_por LRS7360 (confidence=0.87)
```

**Pasos:**
1. Asegúrate de que la relación `LRS7355 reemplaza_por LRS7360` ya tiene
   `confidence >= 0.5` en `knowledge_edges` (repite correcciones si hace
   falta, ver paso 2).
2. Genera un proyecto NUEVO que use el SKU `LRS7355` en un contexto
   parecido al de la corrección original.
3. Si tienes LangSmith activo (ver `backend/.env`, `LANGSMITH_API_KEY`),
   entra a smith.langchain.com, busca el run de esa generación y revisa el
   prompt completo enviado a Claude — debe contener el bloque de arriba.
4. **Verificación funcional:** el proyecto generado debe usar `LRS7360`
   directamente (sin que se lo tengas que corregir de nuevo) — esa es la
   prueba real de que "aprendió".

---

## 6. Pantalla de búsqueda RAG

Ruta: módulo "RAG" del mismo dashboard Flutter
(`frontend/rackbuilder_dashboard/lib/features/rag/`).

**Pasos:**
1. Entra al módulo RAG, botón "Sincronizar" (dispara `POST /rag/sync`,
   corre en segundo plano — el indicador de "en progreso" consulta `GET
   /rag/sync/status`).
2. Espera a que termine (o revisa `knowledge_sync.en_progreso` vía el
   status endpoint).
3. En el panel "Buscar", escribe un texto relacionado con una corrección
   reciente (por ejemplo, parte de la `descripcion_error`).
4. **Verificación:** los resultados deben incluir la corrección indexada
   (con su `tipo = 'correccion'`), confirmando que la corrección quedó
   buscable semánticamente y no solo como fila cruda en la tabla.

---

## Notas

- El ciclo de refuerzo (pasos 1-3) requiere repetir la misma corrección
  varias veces para cruzar los umbrales de `PromotionEngine` — una sola
  corrección no basta para ver candidata/permanente en acción; para
  probar rápido, puedes insertar filas de prueba directamente en
  `knowledge_edges` con `ocurrencias` alto y verificar solo el efecto
  posterior (paso 3 en adelante) sin repetir 50 correcciones reales.
- La sincronización RAG (paso 6) NO es automática — si acabas de registrar
  una corrección y no la encuentras en la búsqueda, primero dispara
  `POST /rag/sync`.
- Si `LANGSMITH_API_KEY` no está configurada en `backend/.env`, el paso 5.3
  (inspeccionar el prompt en LangSmith) no aplica — puedes verificar el
  mismo bloque de texto agregando un log temporal en
  `construir_descripcion_extendida()` en su lugar.
