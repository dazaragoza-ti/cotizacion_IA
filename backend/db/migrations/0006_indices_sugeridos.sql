-- Indices sugeridos por revision senior de BD (Sprint 2, sesion de seguimiento).
--
-- Ambos patrones de consulta ya existen HOY en el codigo y corren sin indice
-- de soporte -- funcionan por el volumen actual (decenas de filas), pero
-- conviene indexarlos antes de que el full-scan se note.

-- 1. correcciones_pm_service._registrar() hace SELECT filtrando por estas
--    3 columnas en cada correccion que se guarda (manual o automatica):
--        .eq("descripcion_error", ...).eq("proyecto_clave", ...).eq("origen", ...)
create index if not exists correcciones_armado_dedup_idx
    on correcciones_armado (descripcion_error, proyecto_clave, origen);

-- 2. KnowledgeGraph.get_relations() (usado por relaciones_relevantes() del
--    Context Builder, en CADA turno con proyecto anterior) filtra por:
--        .eq("from_tipo", tipo).eq("from_id", referencia_id)
create index if not exists knowledge_edges_from_idx
    on knowledge_edges (from_tipo, from_id);
