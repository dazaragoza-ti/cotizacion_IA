import "../entities/estadistica_sku_entity.dart";

abstract class EstadisticasRepository {
  Future<List<EstadisticaSkuEntity>> getTop({required String campo, int limit});
  Future<EstadisticaSkuEntity?> getSku(String sku);
}
