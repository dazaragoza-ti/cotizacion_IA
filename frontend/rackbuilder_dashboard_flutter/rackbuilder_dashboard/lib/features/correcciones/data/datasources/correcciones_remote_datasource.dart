import "../models/correccion_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class CorreccionesRemoteDatasource {
  Future<List<CorreccionModel>> getCorrecciones({int limit});
  Future<void> deleteCorreccion(int correccionId);
}

class CorreccionesRemoteDatasourceImpl implements CorreccionesRemoteDatasource {
  final ApiClient _api;
  const CorreccionesRemoteDatasourceImpl(this._api);

  @override
  Future<List<CorreccionModel>> getCorrecciones({int limit = 100}) async {
    final res = await _api.dio.get("${ApiEndpoints.correcciones}?limit=$limit");
    return ((res.data["correcciones"] as List<dynamic>?) ?? [])
        .map((c) => CorreccionModel.fromJson(c as Map<String, dynamic>)).toList();
  }

  @override
  Future<void> deleteCorreccion(int correccionId) async {
    await _api.dio.delete("${ApiEndpoints.correcciones}/$correccionId");
  }
}
