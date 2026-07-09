import "../entities/rag_resultado_entity.dart";
import "../repositories/rag_repository.dart";

class BuscarRagUsecase {
  final RagRepository _repo;
  const BuscarRagUsecase(this._repo);
  Future<List<RagResultadoEntity>> call({required String query, int topK = 5, String? tipo}) =>
      _repo.search(query: query, topK: topK, tipo: tipo);
}
