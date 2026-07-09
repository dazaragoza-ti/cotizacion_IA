-- Sprint 2 · Fase 5 — Correlación fila ↔ traza de LangSmith
--
-- Permite, dado un registro de disenos_racks, abrir directamente su traza en
-- smith.langchain.com (antes no había forma de ir de una fila guardada al
-- run que la generó, salvo buscar a ojo por fecha/session_id).

alter table disenos_racks
    add column if not exists langsmith_run_id text;
