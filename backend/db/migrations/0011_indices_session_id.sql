-- Indices sobre session_id -- la consulta mas frecuente del sistema (corre
-- en CADA mensaje de Telegram, no solo cuando se genera un proyecto nuevo)
-- y hasta ahora sin indice de soporte (0006_indices_sugeridos.sql cubrio
-- otros dos patrones calientes pero se quedo fuera este).

-- 1. reglas_service.obtener_ultimo_diseno() -- llamado en cada mensaje para
--    saber si hay un diseno previo en esta sesion:
--        .eq("session_id", session_id).order("version_actual", desc=True).limit(1)
create index if not exists disenos_racks_session_version_idx
    on disenos_racks (session_id, version_actual desc);

-- 2. historial_service.ultimo_proyecto_de_sesion() -- mismo proposito,
--    tabla distinta:
--        .eq("session_id", session_id).not_.is_("proyecto_json", "null").order("ts", desc=True).limit(1)
create index if not exists proyectos_pm_historial_session_ts_idx
    on proyectos_pm_historial (session_id, ts desc);
