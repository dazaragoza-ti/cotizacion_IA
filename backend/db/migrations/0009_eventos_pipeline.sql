-- Traza, paso a paso, una solicitud individual mientras avanza por el
-- pipeline real (RAG -> Knowledge Graph -> Context Builder -> Claude ->
-- Engineering -> Generadores). A diferencia de sistema_errores/metricas
-- (agregados), esto permite animar en el mapa de Arquitectura del Sistema
-- por que nodo esta pasando UNA peticion concreta, en el momento en que
-- pasa (via Supabase Realtime, ver 0008_realtime_arquitectura.sql).
create table if not exists eventos_pipeline (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    solicitud_id text not null,
    componente text not null,
    paso text not null,
    estado text not null default 'en_progreso' -- en_progreso | completado | error
);

create index if not exists idx_eventos_pipeline_solicitud
    on eventos_pipeline (solicitud_id, created_at);

-- Idempotente: agrega la tabla a la publicacion de Realtime si no esta ya.
do $$
begin
    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'eventos_pipeline'
    ) then
        alter publication supabase_realtime add table eventos_pipeline;
    end if;
end $$;
