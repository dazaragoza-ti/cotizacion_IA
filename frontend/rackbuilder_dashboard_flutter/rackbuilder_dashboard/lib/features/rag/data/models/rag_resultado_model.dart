import "../../domain/entities/rag_resultado_entity.dart";
class RagResultadoModel extends RagResultadoEntity {
  const RagResultadoModel({required super.tipo, required super.fuente, required super.contenido, required super.similarity});

  factory RagResultadoModel.fromJson(Map<String, dynamic> j) => RagResultadoModel(
    tipo: j["tipo"] as String? ?? "",
    fuente: j["fuente"] as String? ?? "",
    contenido: j["contenido"] as String? ?? "",
    // El RPC match_knowledge (pgvector) puede exponer el score bajo distinto nombre
    // según la migración SQL aplicada — se intentan los alias más comunes.
    similarity: ((j["similarity"] ?? j["similitud"] ?? j["score"]) as num?)?.toDouble() ?? 0.0,
  );
}
