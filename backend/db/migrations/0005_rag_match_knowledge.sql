-- Sistema RAG (pgvector) — función de búsqueda semántica + constraint de upsert.
--
-- Sin este SQL, el sistema RAG en Python no puede funcionar:
--
-- 1. `vector_store.search()` / `repository.search()` llaman al RPC
--    "match_knowledge" — si no existe, cualquier búsqueda revienta con
--    "function match_knowledge does not exist".
--
-- 2. `repository.save_source()` hace un upsert con
--    on_conflict="origen_tabla,origen_id" — sin una restricción única sobre
--    esas 2 columnas, Postgres no sabe qué fila reemplazar y el upsert falla.
--
-- NOTA: ya está aplicada en producción (verificado invocando el RPC en vivo),
-- pero no vivía en el repo como migración versionada. vector(1024) porque
-- EMBEDDING_PROVIDER=voyage (app/ai/rag/config.py) — si cambias a openai
-- (1536 dims), hay que recrear la función Y la columna knowledge_chunks.embedding.

-- 1. Asegurar que la extensión pgvector está habilitada
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Restricción única para que el upsert de knowledge_sources funcione
-- (ALTER TABLE ... ADD CONSTRAINT no soporta IF NOT EXISTS en Postgres;
-- si ya existe al re-aplicar, salta el error 42710 y sigue con el resto).
DO $$
BEGIN
    ALTER TABLE public.knowledge_sources
        ADD CONSTRAINT knowledge_sources_origen_unique UNIQUE (origen_tabla, origen_id);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- 3. La función que hace la búsqueda semántica real (similitud coseno)
CREATE OR REPLACE FUNCTION match_knowledge(
  query_embedding vector(1024),
  match_count int DEFAULT 10,
  filter_tipo text DEFAULT NULL
)
RETURNS TABLE (
  id uuid,
  tipo text,
  fuente text,
  referencia_id text,
  contenido text,
  metadata jsonb,
  similarity float
)
LANGUAGE sql STABLE
AS $$
  SELECT
    knowledge_chunks.id,
    knowledge_chunks.tipo,
    knowledge_chunks.fuente,
    knowledge_chunks.referencia_id,
    knowledge_chunks.contenido,
    knowledge_chunks.metadata,
    1 - (knowledge_chunks.embedding <=> query_embedding) AS similarity
  FROM knowledge_chunks
  WHERE filter_tipo IS NULL OR knowledge_chunks.tipo = filter_tipo
  ORDER BY knowledge_chunks.embedding <=> query_embedding
  LIMIT match_count;
$$;

-- 4. Índice para que la búsqueda no se vuelva lenta al crecer la tabla
--    (ivfflat requiere que ya existan filas; si la tabla está vacía, créalo
--    después de correr el primer /rag/sync).
-- CREATE INDEX IF NOT EXISTS knowledge_chunks_embedding_idx
--   ON public.knowledge_chunks
--   USING ivfflat (embedding vector_cosine_ops)
--   WITH (lists = 100);
