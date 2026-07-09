import "../../domain/entities/diseno_entity.dart";
class DisenoModel extends DisenoEntity {
  const DisenoModel({required super.id, required super.vendedorId, required super.sessionId,
      required super.solicitudOriginal, required super.versionActual,
      required super.historialComentarios, required super.inputTokens,
      required super.outputTokens, required super.createdAt});

  factory DisenoModel.fromJson(Map<String, dynamic> j) => DisenoModel(
    id: j["id"]?.toString() ?? "",
    vendedorId: j["vendedor_id"] as String? ?? "",
    sessionId: j["session_id"] as String? ?? "",
    solicitudOriginal: j["solicitud_original"] as String? ?? "",
    versionActual: (j["version_actual"] as num?)?.toInt() ?? 1,
    historialComentarios: _parseHistorial(j["historial_comentarios"]),
    inputTokens: (j["input_tokens"] as num?)?.toInt() ?? 0,
    outputTokens: (j["output_tokens"] as num?)?.toInt() ?? 0,
    createdAt: j["created_at"] as String? ?? "",
  );

  // Filas antiguas guardaron historial_comentarios como Map en vez de List
  // (bug ya corregido en proyecto_pm_service.py); esto evita que datos legacy
  // rompan la pantalla con un TypeError al castear.
  static List<String> _parseHistorial(dynamic raw) {
    if (raw is List) return raw.map((e) => e.toString()).toList();
    if (raw is Map) {
      final comentario = raw["comentario"];
      return comentario != null ? [comentario.toString()] : [];
    }
    if (raw is String && raw.isNotEmpty) return [raw];
    return [];
  }
}
