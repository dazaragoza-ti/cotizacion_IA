# Notas mínimas de deploy (backend)

## Docker

Desde la raíz del repo:

```bash
docker build -t cotizacion-ia-backend .
docker run --env-file backend/.env -p 8000:8000 cotizacion-ia-backend
```

Healthcheck: `GET /` → `{"status":"healthy",...}` (definido en Dockerfile + `routers/sistema.py`).

## Variables relevantes

- `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- `ANTHROPIC_API_KEY`, `GROQ_API_KEY`
- `VISOR_3D_URL` o `URL_FRONTEND` (visor GitHub Pages)

## Migraciones pendientes de aplicar en Supabase

1. `backend/db/migrations/0012_telegram_sesiones.sql` — persistencia cuestionario/buffers
2. `backend/db/migrations/0013_rls_visor_anon.sql` — policies recomendadas (revisar antes)
3. `backend/db/migrations/0014_jobs_pipeline.sql` — cola opcional `jobs_pipeline` (si falta, enqueue es no-op)

## RAG de fichas técnicas (`tipo=manual`)

Tras desplegar o editar `knowledge/tecnico/*`:

```bash
cd backend
python -c "from app.ai.rag.ingestors.manuales import manuales_ingestor; manuales_ingestor.sync()"
# o POST /rag/sync si el API está arriba
```

Las fichas **no** van embebidas en el system prompt (salvo `EMBED_FICHAS_EN_PROMPT=1`).
Se inyectan por RAG en el turno. Los **casos dorados** (`knowledge/ejemplos/*.json`)
viven solo en disco/git para tests y evaluación — **no** se suben a Supabase.

## Cola async (`jobs_pipeline`)

Al generar un proyecto el orquestador hace `enqueue` best-effort. Sin la tabla
0014 el bot sigue síncrono. Un worker futuro puede `claim` filas `pending`.

## Baseline `0000_baseline.sql`

Si aún no existe el dump, generarlos así (connection string en Settings → Database):

```bash
pg_dump --schema-only --no-owner --no-privileges \
  "postgresql://postgres.<ref>:<password>@aws-0-....pooler.supabase.com:6543/postgres" \
  > backend/db/migrations/0000_baseline.sql
```

No fabricar el baseline a mano.
