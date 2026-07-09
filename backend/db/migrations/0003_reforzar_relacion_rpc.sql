-- Sprint 2 · Fase 3 (cierre) — Upsert atómico de relaciones del grafo
--
-- Antes, CorrectionProcessor._reforzar_relacion hacía select+update desde Python
-- (app/engineering/correction_processor.py), con condición de carrera: dos
-- correcciones concurrentes sobre el mismo par de SKUs podían leer el mismo
-- `ocurrencias` y pisarse el incremento. Este RPC hace insert+incremento+
-- recálculo de confidence en una sola sentencia atómica, apoyado en el índice
-- único de la migración 0002.
--
-- Uso: select * from reforzar_relacion('sku', 'LRS7355', 'reemplaza_por', 'sku', 'LRS7410');

create or replace function reforzar_relacion(
    p_from_tipo          text,
    p_from_id            text,
    p_relation           text,
    p_to_tipo            text,
    p_to_id              text,
    p_correccion_id      integer default null,
    p_origen             text default 'correccion',
    p_umbral_confidence  integer default 30,
    p_umbral_promocion   integer default 50
) returns knowledge_edges
language plpgsql
as $$
declare
    resultado knowledge_edges;
begin
    insert into knowledge_edges (
        from_tipo, from_id, relation, to_tipo, to_id, metadata, confidence, origen, validada
    )
    values (
        p_from_tipo, p_from_id, p_relation, p_to_tipo, p_to_id,
        jsonb_build_object('ocurrencias', 1, 'ultima_correccion_id', p_correccion_id),
        least(0.95, 1.0 / p_umbral_confidence),
        p_origen,
        1 >= p_umbral_promocion
    )
    on conflict (from_tipo, from_id, relation, to_tipo, to_id) do update
        set metadata = jsonb_set(
                jsonb_set(
                    coalesce(knowledge_edges.metadata, '{}'::jsonb),
                    '{ocurrencias}',
                    to_jsonb(coalesce((knowledge_edges.metadata->>'ocurrencias')::integer, 1) + 1)
                ),
                '{ultima_correccion_id}',
                to_jsonb(p_correccion_id)
            ),
            confidence = least(
                0.95,
                (coalesce((knowledge_edges.metadata->>'ocurrencias')::integer, 1) + 1)::float
                    / p_umbral_confidence
            ),
            validada = (coalesce((knowledge_edges.metadata->>'ocurrencias')::integer, 1) + 1) >= p_umbral_promocion
    returning * into resultado;

    return resultado;
end;
$$;
