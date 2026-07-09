import "../../domain/entities/correccion_entity.dart";
import "../../domain/repositories/correcciones_repository.dart";
import "../datasources/correcciones_remote_datasource.dart";

class CorreccionesRepositoryImpl implements CorreccionesRepository {
  final CorreccionesRemoteDatasource _ds;
  const CorreccionesRepositoryImpl(this._ds);
  @override Future<List<CorreccionEntity>> getCorrecciones({int limit = 100}) => _ds.getCorrecciones(limit: limit);
  @override Future<void> deleteCorreccion(int correccionId) => _ds.deleteCorreccion(correccionId);
}
