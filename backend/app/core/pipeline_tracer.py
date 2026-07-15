"""Emite eventos de progreso de UNA solicitud concreta mientras avanza por
el pipeline real (RAG -> Knowledge Graph -> Context Builder -> Claude ->
Engineering -> Generadores), para que el modulo Arquitectura del Sistema
pueda animar en vivo por que nodo va pasando esa peticion (via Supabase
Realtime sobre la tabla eventos_pipeline). Best-effort: nunca debe tumbar
el pipeline real si Supabase esta lento o la tabla no existe todavia."""
import logging

from ..clients import supabase

log = logging.getLogger("pipeline_tracer")


def emitir(solicitud_id: str, componente: str, paso: str, estado: str = "en_progreso") -> None:
    try:
        supabase.table("eventos_pipeline").insert({
            "solicitud_id": solicitud_id,
            "componente": componente,
            "paso": paso,
            "estado": estado,
        }).execute()
    except Exception as e:
        log.warning("No se pudo emitir evento de pipeline (%s/%s): %s", componente, paso, e)
