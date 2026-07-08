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
| `0001_knowledge_stats.sql` | Tabla `knowledge_stats` + RPC `increment_stat` (Sprint 2, Fase 2) | ⬜ pendiente |
| `0002_knowledge_edges_reinforcement.sql` | Índice único para reforzar relaciones (Sprint 2, Fase 3) | ⬜ pendiente |

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
