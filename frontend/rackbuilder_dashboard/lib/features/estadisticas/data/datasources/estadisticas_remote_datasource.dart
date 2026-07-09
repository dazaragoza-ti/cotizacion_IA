import "package:dio/dio.dart";
import "../models/estadistica_sku_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

/// Los 4 campos que knowledge_stats acepta (ver backend/app/engineering/metrics.py).
const List<String> camposEstadisticas = [
  "veces_usado",
  "veces_reemplazado",
  "veces_rechazado",
  "veces_recomendado",
];

abstract class EstadisticasRemoteDatasource {
  Future<List<EstadisticaSkuModel>> getTop({required String campo, int limit = 10});
  Future<EstadisticaSkuModel?> getSku(String sku);
}

class EstadisticasRemoteDatasourceImpl implements EstadisticasRemoteDatasource {
  final ApiClient _api;
  const EstadisticasRemoteDatasourceImpl(this._api);

  @override
  Future<List<EstadisticaSkuModel>> getTop({required String campo, int limit = 10}) async {
    final res = await _api.dio.get(ApiEndpoints.statsTop, queryParameters: {
      "campo": campo,
      "limit": limit,
    });
    return ((res.data["resultados"] as List<dynamic>?) ?? [])
        .map((r) => EstadisticaSkuModel.fromJson(r as Map<String, dynamic>)).toList();
  }

  @override
  Future<EstadisticaSkuModel?> getSku(String sku) async {
    try {
      final res = await _api.dio.get("${ApiEndpoints.statsSku}/$sku");
      return EstadisticaSkuModel.fromJson(res.data as Map<String, dynamic>);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      rethrow;
    }
  }
}
