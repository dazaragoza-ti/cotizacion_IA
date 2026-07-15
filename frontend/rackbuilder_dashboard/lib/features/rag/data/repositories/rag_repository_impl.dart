import "../../domain/entities/rag_resultado_entity.dart";
import "../../domain/repositories/rag_repository.dart";
import "../datasources/rag_remote_datasource.dart";

class RagRepositoryImpl implements RagRepository {
  final RagRemoteDatasource _ds;
  const RagRepositoryImpl(this._ds);

  @override
  Future<List<RagResultadoEntity>> search({required String query, int topK = 5, String? tipo}) =>
      _ds.search(query: query, topK: topK, tipo: tipo);

  @override
  Future<void> sync() => _ds.sync();

  @override
  Future<bool> syncEnProgreso() => _ds.syncEnProgreso();
}
