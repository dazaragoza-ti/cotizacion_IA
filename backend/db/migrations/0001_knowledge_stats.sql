-- Sprint 2 · Fase 2 — Estadísticas por SKU
-- Responde: ¿qué SKU falla más? ¿cuál recomiendan más? ¿cuál reemplazan siempre?
-- Se alimenta desde app/engineering/metrics.py, invocado por el CorrectionProcessor.

create table if not exists knowledge_stats (
    sku                text primary key,
    veces_usado        integer     not null default 0,  -- aparece en un despiece generado
    veces_reemplazado  integer     not null default 0,  -- fue el SKU "viejo" de un reemplazo
    veces_rechazado    integer     not null default 0,  -- eliminado por el usuario en una corrección
    veces_recomendado  integer     not null default 0,  -- fue el SKU "nuevo" de un reemplazo
    ultima_fecha       timestamptz not null default now()
);

-- Incremento atómico (evita el read-modify-write con carrera desde Python).
-- Uso: select increment_stat('LRS7355', 'veces_reemplazado', 1);
create or replace function increment_stat(
    p_sku    text,
    p_campo  text,
    p_delta  integer default 1
) returns void
language plpgsql
as $$
begin
    if p_campo not in (
        'veces_usado', 'veces_reemplazado', 'veces_rechazado', 'veces_recomendado'
    ) then
        raise exception 'campo no permitido: %', p_campo;
    end if;

    execute format(
        'insert into knowledge_stats (sku, %1$I, ultima_fecha)
             values ($1, $2, now())
         on conflict (sku) do update
             set %1$I = knowledge_stats.%1$I + excluded.%1$I,
                 ultima_fecha = now()',
        p_campo
    ) using p_sku, p_delta;
end;
$$;
