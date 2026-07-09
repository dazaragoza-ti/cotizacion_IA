import "../entities/rag_resultado_entity.dart";

abstract class RagRepository {
  Future<List<RagResultadoEntity>> search({required String query, int topK, String? tipo});
  Future<void> sync();
}
