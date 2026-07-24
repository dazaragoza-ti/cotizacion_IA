-- Cola opcional de trabajos del pipeline (generación / regeneración).
-- Idempotente. Si no se aplica en remoto, el código hace best-effort y no bloquea.

create table if not exists jobs_pipeline (
    id uuid primary key default gen_random_uuid(),
    tipo text not null default 'generar_proyecto',
    session_id text,
    tg_user_id bigint,
    payload jsonb not null default '{}'::jsonb,
    estado text not null default 'pending'
        check (estado in ('pending', 'running', 'done', 'error', 'cancelled')),
    error text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    finished_at timestamptz
);

create index if not exists idx_jobs_pipeline_estado_created
    on jobs_pipeline (estado, created_at);

create index if not exists idx_jobs_pipeline_session
    on jobs_pipeline (session_id);

comment on table jobs_pipeline is
    'Cola simple de trabajos async del bot/pipeline. Opcional: sin esta tabla el enqueue es no-op.';
