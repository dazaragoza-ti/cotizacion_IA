# Sprint 2 — Aprendizaje continuo · Estado

> Objetivo del sprint: **cada corrección de un usuario debe hacer mejor al sistema.**
> Una corrección ya no solo se guarda: alimenta embeddings, chunks, grafo,
> compatibility engine, estadísticas, LangSmith y reglas permanentes.
>
> Última actualización: 2026-07-08 · Rama: `josue` · Commit base: `84b8860`

---

## Leyenda de estado

- ✅ **Hecho** — implementado y verificado.
- 🟡 **Parcial** — hay base reutilizable o quedó a medias; falta cerrar.
- ⬜ **Pendiente** — no empezado.
- 🔦 **Necesita infra externa** — depende de aplicar migración en Supabase o de credenciales.

---

## Flujo objetivo

```
Usuario → Claude → Proyecto → Usuario corrige → CorrectionProcessor
                                                   ├── Corrections      (guardar)
                                                   ├── Embeddings/Chunks (RAG)
                                                   ├── KnowledgeGraph    (reemplaza_por / evitar_con / compatible_con)
                                                   ├── CompatibilityEngine (leer grafo)
                                                   ├── Metrics           (knowledge_stats)
                                                   ├── PromotionEngine   (regla permanente → reglas_armado)
                                                   └── LangSmith         (observabilidad + costo)
                                                          ↓
                                        Context Builder LEE el grafo y lo inyecta al prompt
```

---

## Estado por fase

| Fase | Qué hace | Archivo(s) | Estado |
|---|---|---|---|
| 0 — Cimientos | SkuDiffExtractor, planificador puro, convención de migraciones | `sku_diff.py`, `learning.py`, `db/migrations/` | ✅ (0a: `node_modules` fuera del índice, `backend/app` versionado) |
| 1 — Orquestación | CorrectionProcessor punto único de entrada, cableado en el flujo vivo | `correction_processor.py`, `proyecto_pm_service.py` | ✅ |
| 2 — Estadísticas | Contadores por SKU (`knowledge_stats`) + endpoint para consultarlos | `metrics.py`, `routers/stats.py` (`GET /stats/top`, `GET /stats/sku/{sku}`) | ✅ código · 🔦 falta aplicar migración 0001 |
| 3 — Grafo (cierre) | Upsert atómico de aristas, relaciones `evitar_con`/`compatible_con`, lectura del grafo inyectada al prompt | `graph.py` (`upsert_relation`, `relaciones_relevantes`), `learning.py`, `context_builder.py` | ✅ código · 🔦 falta aplicar migraciones 0002/0003 |
| 4 — PromotionEngine | Estados explícitos (nueva→importante→candidata→permanente) y materialización en `reglas_armado` | `promotion.py` | ✅ código · 🔦 depende de 0003 para tener `ocurrencias` reales |
| 5 — LangSmith | Costo (`usage_metadata`), system prompt real en traza, span de retriever, `run_id` en `disenos_racks`, 2ª ruta LLM instrumentada | `tracing.py`, `claude_client.py`, `vector_store.py`, `proyecto_pm_service.py`, `diseno_service.py` | ✅ código · 🔦 falta aplicar migración 0004 |
| Limpieza | `pm_rackbot/*` duplicado muerto, stubs de 0 bytes, normalizador único | — | ✅ eliminado/unificado |

### Qué funciona hoy sin tocar Supabase
- Todo lo de fases 0/1 (ya lo hacía antes de esta ronda).
- El Context Builder consulta `knowledge_edges` en cada turno (si no hay filas para
  un SKU, simplemente no agrega nada — no rompe el flujo).
- El endpoint `/stats/*` responde con 503 explicando qué migración falta, en vez
  de un 500 genérico.

### Qué se activa al aplicar las migraciones pendientes
- **`0001_knowledge_stats.sql`** → contadores reales en `knowledge_stats` y el
  endpoint `/stats/*` deja de dar 503.
- **`0002_knowledge_edges_reinforcement.sql`** → índice único que hace posible
  el upsert atómico.
- **`0003_reforzar_relacion_rpc.sql`** (nueva) → RPC `reforzar_relacion`: sin
  esto, `KnowledgeGraph.upsert_relation()` falla (best-effort, se loguea) y
  ninguna relación se refuerza ni se promueve.
- **`0004_disenos_racks_langsmith_run_id.sql`** (nueva) → columna
  `langsmith_run_id`; sin ella, el `insert` a `disenos_racks` sigue funcionando
  igual (no se ve afectado) pero el `update` posterior falla silenciosamente y
  no queda la correlación fila↔traza.

## 🔦 Pendiente de infra externa (requiere acción manual del usuario)

Las 4 migraciones (`0001`–`0004`, en `backend/db/migrations/`) están **redactadas
pero no aplicadas** en Supabase. No se pudieron aplicar automáticamente en esta
ronda porque `SUPABASE_URL`/`SUPABASE_KEY` en `.env` son credenciales de la API
REST — aplicar DDL (`create table`, `create function`, `alter table`) requiere
una conexión directa a Postgres (Settings → Database → Connection string) o
pegar el SQL a mano en el SQL Editor de Supabase. Pasos:

```bash
# Opción A — psql directo (requiere la contraseña de la BD, no el anon/service key)
psql "postgresql://postgres:<password>@db.<project-ref>.supabase.co:5432/postgres" \
  -f backend/db/migrations/0001_knowledge_stats.sql \
  -f backend/db/migrations/0002_knowledge_edges_reinforcement.sql \
  -f backend/db/migrations/0003_reforzar_relacion_rpc.sql \
  -f backend/db/migrations/0004_disenos_racks_langsmith_run_id.sql

# Opción B — SQL Editor de Supabase: pegar cada archivo, en orden, y ejecutar.
```

También sigue pendiente el baseline (`0000_baseline.sql`, `pg_dump --schema-only`)
mencionado en `backend/db/migrations/README.md` — mismo bloqueo de credenciales.

Nota: `0005_rag_match_knowledge.sql` (RPC `match_knowledge` del sistema RAG) es una migración *distinta*, no pendiente — se rescató de un archivo suelto en la raíz del repo y se confirmó aplicada en vivo durante el merge con `origin/josue`. Ver `AI_ENGINEERING_MANUAL.md` para el historial completo de esa reconciliación.

---

## Decisiones tomadas en esta ronda
- **Umbral de confidence:** confirmado 30 (confidence máx ≈0.95) / 50 (promoción
  a permanente), tal como ya estaba en el código.
- **`node_modules` en git:** sacado del índice (no del disco) y agregado a `.gitignore`.
- **Heurística v1 de `evitar_con`/`compatible_con`** (nueva, documentada en
  `learning.py`): cuando un reemplazo ocurre, el SKU nuevo se marca
  `compatible_con` las piezas de OTRA familia que sobrevivieron sin cambio en el
  proyecto corregido (máx. 5 por corrección, para no generar aristas O(n²)).
  Cuando una pieza se elimina sin sustituto, se marca `evitar_con` esas mismas
  piezas de contexto — señal conservadora, a validar con datos reales conforme
  se acumulen correcciones.

## Decisiones abiertas (a confirmar)
- **Emparejamiento viejo↔nuevo** cuando cambian varias piezas: v1 solo empareja 1↔1 por familia; los casos N↔M quedan como altas/bajas sueltas.
- **Bug preexistente detectado (fuera de alcance de este sprint):**
  `app/services/diseno_service.py` importa `consultar_reglas_armado` y
  `consultar_correcciones_relevantes` desde `reglas_service.py`, pero esas
  funciones no existen ahí — el módulo falla al importarse. No rompe nada hoy
  porque nada más lo importa (código muerto/inalcanzable), pero si se planea
  reactivar el "Agente de Ensamble rápido" hay que resolverlo primero.

---

## Cómo probar lo hecho
```bash
cd backend
python tests/test_sku_diff.py     # 6 tests
python tests/test_learning.py     # 6 tests (incluye evitar_con/compatible_con)
```
El flujo end-to-end (guardar corrección real → métricas → grafo → promoción →
contexto inyectado a Claude) requiere credenciales de Supabase/Anthropic/Voyage
(ya en `.env`) y aplicar las migraciones `0001`–`0004` (ver sección de infra
externa arriba).
