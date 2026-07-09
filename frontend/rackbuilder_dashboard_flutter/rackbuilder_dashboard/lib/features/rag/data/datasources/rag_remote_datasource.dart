import "../models/rag_resultado_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class RagRemoteDatasource {
  Future<void> sincronizar();
  Future<List<RagResultadoModel>> buscar({required String query, int topK, String? tipo});
}

class RagRemoteDatasourceImpl implements RagRemoteDatasource {
  final ApiClient _api;
  const RagRemoteDatasourceImpl(this._api);

  @override
  Future<void> sincronizar() async {
    await _api.dio.post(ApiEndpoints.ragSync);
  }

  @override
  Future<List<RagResultadoModel>> buscar({required String query, int topK = 5, String? tipo}) async {
    final res = await _api.dio.get(ApiEndpoints.ragSearch, queryParameters: {
      "q": query, "top_k": topK, if (tipo != null && tipo.isNotEmpty) "tipo": tipo,
    });
    return ((res.data["resultados"] as List<dynamic>?) ?? [])
        .map((r) => RagResultadoModel.fromJson(r as Map<String, dynamic>)).toList();
  }
}
