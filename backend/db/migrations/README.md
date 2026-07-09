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
| `0006_indices_sugeridos.sql` | Índices sobre `correcciones_armado` y `knowledge_edges` (revisión senior de BD) | ⬜ pendiente |

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
