import "../entities/rag_resultado_entity.dart";
abstract class RagRepository {
  Future<void> sincronizar();
  Future<List<RagResultadoEntity>> buscar({required String query, int topK, String? tipo});
}
