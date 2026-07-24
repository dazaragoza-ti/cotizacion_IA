# Migraciones de base de datos (Supabase / Postgres)

Antes del Sprint 2 el esquema vivía **solo** en el proyecto remoto de Supabase
(cero archivos `.sql` en el repo). Aquí empezamos a versionarlo.

## Convención

- Archivos numerados: `NNNN_descripcion.sql`, aplicados en orden ascendente.
- Cada migración es **idempotente** cuando es posible (`if not exists`,
  `create or replace`), para poder re-aplicarla sin romper.
- Se aplican manualmente en el SQL Editor de Supabase (o vía `psql`) hasta que
  se automatice. Anota en el PR qué migraciones se aplicaron.

## Estado

| Archivo | Contenido | ¿Aplicada en prod? |
|---|---|---|
| `0000_baseline.sql` | Esquema actual (pendiente de volcar desde Supabase) | — |
| `0001_knowledge_stats.sql` | Tabla `knowledge_stats` + RPC `increment_stat` (Sprint 2, Fase 2) | ✅ aplicada (verificado en vivo — corrige el estado anterior, que la daba por pendiente) |
| `0002_knowledge_edges_reinforcement.sql` | Índice único para reforzar relaciones (Sprint 2, Fase 3) | ✅ aplicada (confirmado indirecto: `0003` funciona en vivo y su `on conflict` requiere este índice) |
| `0003_reforzar_relacion_rpc.sql` | RPC `reforzar_relacion` — upsert atómico de aristas (Sprint 2, Fase 3, cierre) | ✅ aplicada (verificado en vivo, invocacion real exitosa) |
| `0004_disenos_racks_langsmith_run_id.sql` | Columna `langsmith_run_id` en `disenos_racks` (Sprint 2, Fase 5) | ✅ aplicada (verificado en vivo) |
| `0005_rag_match_knowledge.sql` | RPC `match_knowledge` + constraint única de `knowledge_sources` (sistema RAG) | ✅ aplicada (verificado en vivo) |
| `0006_indices_sugeridos.sql` | Índices sobre `correcciones_armado` y `knowledge_edges` (revisión senior de BD) | ❓ no verificable sin SQL (`pg_indexes`); tablas base existen — re-aplicar el `.sql` (idempotente) en SQL Editor si el SELECT no los lista |
| `0007_sistema_errores.sql` | Tabla `sistema_errores` (fallos del backend para Arquitectura del Sistema) | ✅ aplicada (verificado en vivo) |
| `0008_realtime_arquitectura.sql` | Agrega `sistema_errores`, `knowledge_edges`, `knowledge_chunks`, `reglas_armado`, `disenos_racks` a la publicación `supabase_realtime` (mapa de Arquitectura en vivo vía websocket) | ✅ aplicada (verificado en vivo: Realtime `postgres_changes` OK en esas tablas) |
| `0009_eventos_pipeline.sql` | Tabla `eventos_pipeline` (traza paso a paso de una solicitud individual) + publicación Realtime | ✅ aplicada (verificado en vivo: tabla con datos + Realtime OK; índice `idx_eventos_pipeline_solicitud` no confirmado por SQL) |
| `0010_clientes.sql` | Tabla `clientes` (Cotizador IA: historial de compras para descuentos) + `cliente_id` en `proyectos_pm_historial` | ✅ aplicada (verificado en vivo: tabla `clientes` + columna `cliente_id`; índices de la migración no confirmados por SQL) |
| `0011_indices_session_id.sql` | Índices sobre `session_id` en `disenos_racks` y `proyectos_pm_historial` (la consulta más frecuente del sistema, sin cubrir) | ❓ no verificable sin SQL (`pg_indexes`); columnas `session_id` existen — re-aplicar el `.sql` (idempotente) en SQL Editor si el SELECT no los lista |

## Pendiente: baseline (0000)

El baseline del esquema **existente** aún no está en el repo porque debe
volcarse desde la BD real (no se debe fabricar a mano — los tipos de columna
solo se infirieron del código). Generarlo con, p.ej.:

```bash
# Requiere la connection string de Supabase (Settings > Database)
pg_dump --schema-only --no-owner --no-privileges \
  "postgresql://...supabase..." > backend/db/migrations/0000_baseline.sql
```

Tablas que el código ya usa hoy (referencia, para validar el dump):
`knowledge_chunks`, `knowledge_sources`, `knowledge_entities`,
`knowledge_edges`, `catalogo_pm`, `catalogo_piezas`, `reglas_armado`,
`correcciones_armado`, `proyectos_pm`, `proyectos_pm_historial`,
`disenos_racks`, `cotizaciones`; y el RPC `match_knowledge` (pgvector).
