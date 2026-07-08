-- Sprint 2 · Fase 3 — Reforzamiento de relaciones del grafo
--
-- Hoy KnowledgeGraph.add_relation() hace INSERT siempre (app/ai/rag/graph.py:62),
-- así que la misma relación repetida se DUPLICA en vez de reforzarse. Para poder
-- hacer upsert (incrementar ocurrencias + recalcular confidence) necesitamos una
-- clave única sobre la arista lógica.
--
-- La arista se identifica por (from_tipo, from_id, relation, to_tipo, to_id).
-- Con este índice único, el nuevo upsert_relation() podrá:
--   on conflict (...) do update set
--     metadata = jsonb_set(..., 'ocurrencias', ocurrencias+1),
--     confidence = least(0.95, (ocurrencias+1)::float / <UMBRAL>)

-- Nota: si ya existen filas duplicadas en prod, deduplicar antes de crear el índice
-- (conservar la de mayor confidence / más reciente). Ver README.

create unique index if not exists knowledge_edges_arista_unica
    on knowledge_edges (from_tipo, from_id, relation, to_tipo, to_id);
