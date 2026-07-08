# Sprint 2 — Aprendizaje continuo · Estado

> Objetivo del sprint: **cada corrección de un usuario debe hacer mejor al sistema.**
> Una corrección ya no solo se guarda: alimenta embeddings, chunks, grafo,
> compatibility engine, estadísticas, LangSmith y (a futuro) reglas permanentes.
>
> Última actualización: 2026-07-08 · Rama: `josue` · Commit base: `5ce7120`

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
                                                   ├── KnowledgeGraph    (reemplaza_por…)
                                                   ├── CompatibilityEngine (leer grafo)
                                                   ├── Metrics           (knowledge_stats)
                                                   ├── PromotionEngine   (regla permanente)
                                                   └── LangSmith         (observabilidad)
```

---

## Lo que YA se implementó (este sprint)

| Componente | Archivo | Estado | Nota |
|---|---|---|---|
| **SkuDiffExtractor** | `backend/app/engineering/sku_diff.py` | ✅ | Extrae reemplazos/altas/bajas/cambios de cantidad desde el JSON antes/después. Normaliza sufijos de color. **Pieza fundacional.** |
| **Planificador de aprendizaje** (puro) | `backend/app/engineering/learning.py` | ✅ | `DiffSku → PlanAprendizaje` (métricas + relaciones). Sin I/O → testeable. |
| **MetricsService** | `backend/app/engineering/metrics.py` | 🟡🔦 | Incrementa `knowledge_stats` vía RPC atómico. Best-effort: no-op con aviso hasta aplicar migración `0001`. |
| **CorrectionProcessor** | `backend/app/engineering/correction_processor.py` | ✅ | Punto único de entrada. Orquesta guardar→diff→métricas→grafo→promoción. Todo best-effort. |
| **Cableado en el flujo vivo** | `backend/app/services/proyecto_pm_service.py` | ✅ | 3 puntos: corrección manual (`process`), automática (`process_automatica`), conteo de uso (`registrar_uso`). |
| **Escritura de grafo `reemplaza_por`** | dentro de `correction_processor.py` | 🟡 | **Escribe** aristas SKU→SKU con `confidence` reforzada (umbral 30→0.95) y marca `validada` a las 50 ocurrencias. La tabla `knowledge_edges` ya existía. |
| **Migración `knowledge_stats`** | `backend/db/migrations/0001_knowledge_stats.sql` | 🔦 | Tabla + RPC `increment_stat`. **Autorada, no aplicada.** |
| **Migración índice de reforzamiento** | `backend/db/migrations/0002_knowledge_edges_reinforcement.sql` | 🔦 | Índice único para upsert atómico de relaciones. **Autorada, no aplicada.** |
| **Convención de migraciones** | `backend/db/migrations/README.md` | ✅ | Antes había cero `.sql` en el repo. |
| **Tests** | `backend/tests/test_sku_diff.py`, `test_learning.py` | ✅ | 10/10 en verde. Corren con `python` plano (sin pytest). |

### Qué funciona hoy sin tocar Supabase
- Detección de corrección + guardado en `correcciones_armado` (ya existía).
- Indexación de embeddings en vivo (ya existía, dentro de `registrar_correccion`).
- Cálculo del diff de SKUs.
- Escritura de aristas `reemplaza_por` en `knowledge_edges` (tabla ya existente).

### Qué se activa al aplicar la migración `0001`
- Los contadores de `knowledge_stats` (hoy solo loguean aviso).

---

## Lo que ya existía en el proyecto (base reutilizable, NO nuevo)

| Subsistema | Dónde | Estado antes del sprint |
|---|---|---|
| Guardado de correcciones | `app/services/correcciones_pm_service.py` (`_registrar`) | ✅ tabla `correcciones_armado`, dedup por `veces_repetida` |
| Embeddings / RAG (pgvector) | `app/ai/rag/` (Voyage, `knowledge_chunks`, RPC `match_knowledge`) | ✅ funcionando; recupera `tipo="correccion"` |
| Grafo de conocimiento (tablas) | `app/ai/rag/graph.py` (`knowledge_entities`, `knowledge_edges`) | 🟡 write-only, `confidence` hardcodeada, sin `reemplaza_por` |
| Compatibility Engine | `app/engineering/compatibility.py` | 🟡 100% estático/determinista, no aprende |
| LangSmith / tracing | `app/ai/tracing.py`, `app/ai/clients/claude_client.py:100` | 🟡 un solo `@traceable`, sin costo ni retrieval |

---

## Lo que FALTA (pendiente)

### Fase 0 — Cimientos
- ⬜ **0a (resto):** versionar TODO `backend/app` y sacar `node_modules/` del índice (hoy commiteados, ~3.600 archivos). Se hizo un commit **acotado** solo a los archivos del sprint; el resto de la app sigue untracked en la rama `josue`.
- 🔦 **0d (baseline):** volcar el esquema actual de Supabase a `0000_baseline.sql` con `pg_dump` (no se debe fabricar a mano).

### Fase 2 — Estadísticas
- 🔦 Aplicar `0001_knowledge_stats.sql` en Supabase.
- ⬜ Endpoint/consulta para responder "¿qué SKU falla/recomiendan/reemplazan más?" (la tabla ya se llenará; falta exponerlo).

### Fase 3 — Aprendizaje + grafo (cerrar el bucle) ← **siguiente sugerido**
- 🟡 La escritura de `reemplaza_por` ya está; falta el **upsert atómico** (aplicar `0002` y migrar el select+update actual a `on conflict`).
- ⬜ **Cerrar el bucle de LECTURA:** que `app/ai/context_builder.py` (o `compatibility.py`) lea `knowledge_graph.get_relations(sku)` e inyecte al prompt de Claude (ej. *"LRS7355 suele reemplazarse por LRS7410, confidence 0.9"*). **Hoy el grafo es write-only — sin esto no aporta valor al modelo.**
- ⬜ Relaciones `evitar_con` / `compatible_con` (además de `reemplaza_por`).

### Fase 4 — PromotionEngine
- 🟡 Hoy solo se marca `validada=True` al llegar a 50 ocurrencias, dentro del processor.
- ⬜ Motor explícito con estados intermedios (1→5 importante→20 candidata→50 permanente) y **materialización a `reglas_armado`** (tabla que el RAG ya consume).

### Fase 5 — LangSmith / observabilidad
- ⬜ Span `run_type="retriever"` en `app/ai/rag/search.py` (top_k, scores, IDs de chunk).
- ⬜ Mapear tokens a `usage_metadata` para que LangSmith calcule **costo**.
- ⬜ Incluir el **system prompt real** en la traza.
- ⬜ Persistir el `run_id` en `disenos_racks` para correlacionar fila ↔ traza.
- ⬜ Trazar la 2ª ruta LLM sin instrumentar (`app/services/diseno_service.py:265`).

### Limpieza / deuda técnica
- ⬜ Eliminar el duplicado muerto `app/services/pm_rackbot/*` (el canónico es `app/services/*`).
- ⬜ Vaciar/decidir stubs de 0 bytes: `app/engineering/{corrections,rules,replacements,recommendations,engine}.py`, `app/graph/*`, `app/models/knowledge.py`, `app/schemas/{knowledge,graph}.py`.
- ⬜ Unificar `normalizar_sku` (sku_diff) con `_codigo_base` (validator_engine) en un único normalizador.

---

## Decisiones abiertas (a confirmar)
- **Umbral de confidence:** hoy `confidence = min(0.95, ocurrencias/30)` y promoción a permanente en 50. El brief mencionaba 30 y 50 — confirmar.
- **Emparejamiento viejo↔nuevo** cuando cambian varias piezas: v1 solo empareja 1↔1 por familia; los casos N↔M quedan como altas/bajas sueltas.
- **`node_modules` en git:** ¿sacarlos del control de versiones? (recomendado).

---

## Cómo probar lo hecho
```bash
cd backend
python tests/test_sku_diff.py     # 6 tests
python tests/test_learning.py     # 4 tests
```
El flujo end-to-end (guardar corrección real → métricas → grafo) requiere
credenciales de Supabase/Anthropic/Voyage y aplicar las migraciones `0001`/`0002`.
