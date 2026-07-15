-- Habilita Supabase Realtime (WAL -> websocket) sobre las tablas que el
-- modulo "Arquitectura del Sistema" del frontend vigila en vivo, para que
-- el mapa se actualice al instante en vez de esperar el polling de 30s.
-- Idempotente: si la tabla ya esta en la publicacion, no falla.
do $$
begin
    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'sistema_errores'
    ) then
        alter publication supabase_realtime add table sistema_errores;
    end if;

    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'knowledge_edges'
    ) then
        alter publication supabase_realtime add table knowledge_edges;
    end if;

    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'knowledge_chunks'
    ) then
        alter publication supabase_realtime add table knowledge_chunks;
    end if;

    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'reglas_armado'
    ) then
        alter publication supabase_realtime add table reglas_armado;
    end if;

    if not exists (
        select 1 from pg_publication_tables
        where pubname = 'supabase_realtime' and tablename = 'disenos_racks'
    ) then
        alter publication supabase_realtime add table disenos_racks;
    end if;
end $$;
