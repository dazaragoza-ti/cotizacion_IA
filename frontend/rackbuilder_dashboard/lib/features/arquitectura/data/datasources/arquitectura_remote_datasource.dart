import "../../domain/error_sistema.dart";
import "../../../../core/network/api_client.dart";

abstract class ArquitecturaRemoteDatasource {
  Future<List<ErrorSistema>> getErroresActivos();
  Future<void> resolverError(String id);
}

class ArquitecturaRemoteDatasourceImpl implements ArquitecturaRemoteDatasource {
  final ApiClient _api;
  const ArquitecturaRemoteDatasourceImpl(this._api);

  @override
  Future<List<ErrorSistema>> getErroresActivos() async {
    final res = await _api.dio.get("/sistema/errores", queryParameters: {
      "limit": 20,
      "solo_activos": true,
    });
    return ((res.data["errores"] as List<dynamic>?) ?? [])
        .map((e) => ErrorSistema.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  Future<void> resolverError(String id) async {
    await _api.dio.post("/sistema/errores/$id/resolver");
  }
}
