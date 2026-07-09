-- Persiste errores del backend (excepciones no manejadas y respuestas 5xx)
-- para que el modulo "Arquitectura del Sistema" del frontend los muestre
-- sobre el mapa de componentes en tiempo real.
create table if not exists sistema_errores (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    componente text not null,
    endpoint text,
    mensaje text not null,
    resuelto boolean not null default false
);

create index if not exists idx_sistema_errores_activos
    on sistema_errores (resuelto, created_at desc);
