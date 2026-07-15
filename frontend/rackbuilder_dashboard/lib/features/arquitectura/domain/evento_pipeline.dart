/// Un paso concreto de UNA solicitud en curso (no un agregado): "la
/// peticion X esta ahora mismo en Claude", a diferencia de las metricas
/// (contadores) o los errores del sistema. Viene de Supabase Realtime
/// (tabla eventos_pipeline, ver backend/app/core/pipeline_tracer.py).
class EventoPipeline {
  final String solicitudId;
  final String componente;
  final String paso;
  final String estado; // en_progreso | completado | error

  const EventoPipeline({
    required this.solicitudId,
    required this.componente,
    required this.paso,
    required this.estado,
  });

  factory EventoPipeline.fromJson(Map<String, dynamic> json) => EventoPipeline(
    solicitudId: json["solicitud_id"] as String? ?? "",
    componente: json["componente"] as String? ?? "",
    paso: json["paso"] as String? ?? "",
    estado: json["estado"] as String? ?? "en_progreso",
  );
}
