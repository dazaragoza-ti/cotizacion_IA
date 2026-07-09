import "../entities/estadistica_sku_entity.dart";
import "../repositories/estadisticas_repository.dart";

class GetTopEstadisticasUsecase {
  final EstadisticasRepository _repo;
  const GetTopEstadisticasUsecase(this._repo);
  Future<List<EstadisticaSkuEntity>> call({required String campo, int limit = 10}) =>
      _repo.getTop(campo: campo, limit: limit);
}
