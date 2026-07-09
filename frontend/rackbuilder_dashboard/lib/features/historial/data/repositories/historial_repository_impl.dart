import "../../domain/entities/diseno_entity.dart";
import "../../domain/repositories/historial_repository.dart";
import "../datasources/historial_remote_datasource.dart";

class HistorialRepositoryImpl implements HistorialRepository {
  final HistorialRemoteDatasource _ds;
  const HistorialRepositoryImpl(this._ds);
  @override Future<List<DisenoEntity>> getHistorial({int limit = 50}) => _ds.getHistorial(limit: limit);
  @override Future<List<DisenoEntity>> getVersionesSesion(String s) => _ds.getVersionesSesion(s);
}
