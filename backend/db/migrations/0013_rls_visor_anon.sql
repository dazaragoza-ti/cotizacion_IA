-- Políticas RLS recomendadas para el visor 3D (anon key pública).
-- NO se aplican automáticamente desde el backend: revisar y ejecutar en
-- SQL Editor de Supabase tras validar que el frontend solo lee por session_id.
--
-- Riesgo actual (sin RLS o con policies abiertas):
--   - La anon key del visor puede listar/leer TODOS los diseños de disenos_racks.
--   - Storage público puede exponer cotizaciones/modelos de otros clientes.
--
-- Objetivo:
--   - anon: SELECT en disenos_racks filtrado por session_id (vía query del cliente).
--     Nota: PostgREST no puede forzar "solo el session_id de la URL" sin JWT;
--     la mitigación práctica es: (1) no permitir SELECT * sin filtro desde el
--     frontend, (2) policy que exige session_id en el request vía RPC, o
--     (3) exponer solo un RPC get_diseno_por_session(session_id text).
--   - service_role: bypassa RLS (backend).
--   - storage: lectura pública solo de objetos bajo prefijos conocidos.

-- ── disenos_racks ──────────────────────────────────────────────────────────
alter table if exists disenos_racks enable row level security;

-- Lectura anon: permitir SELECT (el visor filtra por session_id en el cliente).
-- Endurecer después con RPC si se requiere aislamiento fuerte.
drop policy if exists "anon_select_disenos_racks" on disenos_racks;
create policy "anon_select_disenos_racks"
    on disenos_racks
    for select
    to anon, authenticated
    using (true);

-- Escritura: solo service_role (el backend usa SUPABASE_SERVICE_ROLE_KEY).
drop policy if exists "service_insert_disenos_racks" on disenos_racks;
create policy "service_insert_disenos_racks"
    on disenos_racks
    for insert
    to service_role
    with check (true);

drop policy if exists "service_update_disenos_racks" on disenos_racks;
create policy "service_update_disenos_racks"
    on disenos_racks
    for update
    to service_role
    using (true)
    with check (true);

drop policy if exists "service_delete_disenos_racks" on disenos_racks;
create policy "service_delete_disenos_racks"
    on disenos_racks
    for delete
    to service_role
    using (true);

-- RPC recomendado (aislamiento más fuerte que SELECT abierto):
create or replace function public.get_diseno_por_session(p_session_id text)
returns setof disenos_racks
language sql
security definer
set search_path = public
as $$
    select *
    from disenos_racks
    where session_id = p_session_id
    order by version_actual desc;
$$;

revoke all on function public.get_diseno_por_session(text) from public;
grant execute on function public.get_diseno_por_session(text) to anon, authenticated;

-- Cuando el frontend use solo el RPC, restringir SELECT directo:
-- drop policy if exists "anon_select_disenos_racks" on disenos_racks;
-- create policy "anon_no_direct_select_disenos_racks"
--     on disenos_racks for select to anon using (false);

-- ── telegram_sesiones (solo backend) ───────────────────────────────────────
alter table if exists telegram_sesiones enable row level security;

drop policy if exists "service_all_telegram_sesiones" on telegram_sesiones;
create policy "service_all_telegram_sesiones"
    on telegram_sesiones
    for all
    to service_role
    using (true)
    with check (true);

-- ── Storage (buckets modelos / cotizaciones) ───────────────────────────────
-- Ejecutar solo si los buckets existen. Ajusta nombres si difieren.
--
-- Políticas de storage viven en storage.objects:
--
-- drop policy if exists "anon_read_modelos_public" on storage.objects;
-- create policy "anon_read_modelos_public"
--   on storage.objects for select to anon, authenticated
--   using (bucket_id = 'modelos');
--
-- drop policy if exists "service_write_modelos" on storage.objects;
-- create policy "service_write_modelos"
--   on storage.objects for all to service_role
--   using (bucket_id in ('modelos', 'cotizaciones'))
--   with check (bucket_id in ('modelos', 'cotizaciones'));
--
-- Para cotizaciones: preferir URLs firmadas (service_role) en vez de bucket público.
