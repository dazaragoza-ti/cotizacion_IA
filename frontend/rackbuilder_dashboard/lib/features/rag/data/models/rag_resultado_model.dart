import "../../domain/entities/rag_resultado_entity.dart";

class RagResultadoModel extends RagResultadoEntity {
  const RagResultadoModel({
    required super.tipo,
    required super.fuente,
    required super.referenciaId,
    required super.contenido,
    required super.similarity,
  });

  factory RagResultadoModel.fromJson(Map<String, dynamic> j) {
    // similarity puede llegar como NaN (json invalido) si el embedding de
    // consulta no se pudo comparar -- se normaliza a 0.
    final rawSim = j["similarity"];
    final sim = rawSim is num && rawSim.isFinite ? rawSim.toDouble() : 0.0;
    return RagResultadoModel(
      tipo: j["tipo"] as String? ?? "",
      fuente: j["fuente"] as String? ?? "",
      referenciaId: j["referencia_id"] as String? ?? "",
      contenido: j["contenido"] as String? ?? "",
      similarity: sim,
    );
  }
}
