import "../entities/estadistica_sku_entity.dart";
import "../entities/correccion_entity.dart";

abstract class EstadisticasRepository {
  Future<List<EstadisticaSkuEntity>> getTop({required String campo, int limit});
  Future<EstadisticaSkuEntity?> getSku(String sku);
  Future<List<CorreccionEntity>> getCorrecciones({int limit});
}
