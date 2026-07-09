import "../../domain/entities/rag_resultado_entity.dart";
import "../../domain/repositories/rag_repository.dart";
import "../datasources/rag_remote_datasource.dart";

class RagRepositoryImpl implements RagRepository {
  final RagRemoteDatasource _ds;
  const RagRepositoryImpl(this._ds);
  @override Future<void> sincronizar() => _ds.sincronizar();
  @override Future<List<RagResultadoEntity>> buscar({required String query, int topK = 5, String? tipo}) =>
      _ds.buscar(query: query, topK: topK, tipo: tipo);
}
