-- Cotizador IA / Ventas (Cap. 7.12 del manual: unico caso que justifica un
-- segundo agente, porque razona sobre un dominio de negocio -- descuentos,
-- historial de cliente -- no sobre ingenieria de racks).
--
-- No existia ninguna nocion de "cliente" mas alla de un texto libre en cada
-- proyecto (proyectos_pm_historial.cliente). Esta tabla junta pedidos del
-- mismo cliente para poder calcular descuentos por historial de compras.
create table if not exists clientes (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    nombre text not null,
    nombre_normalizado text not null,
    telefono text,
    monto_total_historico numeric not null default 0,
    numero_pedidos integer not null default 0
);

create index if not exists idx_clientes_nombre_normalizado on clientes (nombre_normalizado);
create unique index if not exists idx_clientes_telefono on clientes (telefono) where telefono is not null;

-- Liga cada registro del historial tecnico a un cliente (nullable: los
-- registros viejos no tienen cliente_id, se resuelve solo hacia adelante).
alter table proyectos_pm_historial add column if not exists cliente_id uuid references clientes(id);
create index if not exists idx_proyectos_pm_historial_cliente on proyectos_pm_historial (cliente_id);
