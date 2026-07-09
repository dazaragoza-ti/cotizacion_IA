import "../entities/estadistica_sku_entity.dart";
import "../repositories/estadisticas_repository.dart";

class GetEstadisticaSkuUsecase {
  final EstadisticasRepository _repo;
  const GetEstadisticaSkuUsecase(this._repo);
  Future<EstadisticaSkuEntity?> call(String sku) => _repo.getSku(sku);
}
