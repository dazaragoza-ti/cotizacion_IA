-- Persistencia de cuestionario + buffers de Telegram (TTL).
-- Idempotente. Aplicar en SQL Editor de Supabase.

create table if not exists telegram_sesiones (
    chat_id text primary key,
    user_id bigint,
    estado_cuestionario jsonb not null default '{}'::jsonb,
    buffers jsonb not null default '{"imagenes":[],"pdfs":[],"capciones":[]}'::jsonb,
    updated_at timestamptz not null default now(),
    expires_at timestamptz not null default (now() + interval '24 hours')
);

create index if not exists idx_telegram_sesiones_expires
    on telegram_sesiones (expires_at);

comment on table telegram_sesiones is
    'Estado del cuestionario y adjuntos pendientes por chat de Telegram. TTL 24h; /cancelar borra la fila.';

-- Limpieza opcional (programar en cron / pg_cron si está disponible):
-- delete from telegram_sesiones where expires_at < now();
