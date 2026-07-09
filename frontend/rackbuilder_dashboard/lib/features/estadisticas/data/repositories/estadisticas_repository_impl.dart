import "../../domain/entities/estadistica_sku_entity.dart";
import "../../domain/repositories/estadisticas_repository.dart";
import "../datasources/estadisticas_remote_datasource.dart";

class EstadisticasRepositoryImpl implements EstadisticasRepository {
  final EstadisticasRemoteDatasource _ds;
  const EstadisticasRepositoryImpl(this._ds);

  @override
  Future<List<EstadisticaSkuEntity>> getTop({required String campo, int limit = 10}) =>
      _ds.getTop(campo: campo, limit: limit);

  @override
  Future<EstadisticaSkuEntity?> getSku(String sku) => _ds.getSku(sku);
}
