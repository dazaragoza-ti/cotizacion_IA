import "../models/rag_resultado_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class RagRemoteDatasource {
  Future<List<RagResultadoModel>> search({required String query, int topK = 5, String? tipo});
  Future<void> sync();
}

class RagRemoteDatasourceImpl implements RagRemoteDatasource {
  final ApiClient _api;
  const RagRemoteDatasourceImpl(this._api);

  @override
  Future<List<RagResultadoModel>> search({required String query, int topK = 5, String? tipo}) async {
    final res = await _api.dio.get(ApiEndpoints.ragSearch, queryParameters: {
      "q": query,
      "top_k": topK,
      if (tipo != null && tipo.isNotEmpty) "tipo": tipo,
    });
    return ((res.data["resultados"] as List<dynamic>?) ?? [])
        .map((r) => RagResultadoModel.fromJson(r as Map<String, dynamic>)).toList();
  }

  @override
  Future<void> sync() async {
    await _api.dio.post(ApiEndpoints.ragSync);
  }
}
