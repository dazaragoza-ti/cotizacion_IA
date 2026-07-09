import "package:dio/dio.dart";
import "../models/diseno_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class HistorialRemoteDatasource {
  Future<List<DisenoModel>> getHistorial({int limit});
  Future<List<DisenoModel>> getVersionesSesion(String sessionId);
}

class HistorialRemoteDatasourceImpl implements HistorialRemoteDatasource {
  final ApiClient _api;
  const HistorialRemoteDatasourceImpl(this._api);

  @override
  Future<List<DisenoModel>> getHistorial({int limit = 50}) async {
    final res = await _api.dio.get("${ApiEndpoints.disenosHistorial}?limit=$limit");
    return ((res.data["disenos"] as List<dynamic>?) ?? [])
        .map((d) => DisenoModel.fromJson(d as Map<String, dynamic>)).toList();
  }

  @override
  Future<List<DisenoModel>> getVersionesSesion(String sessionId) async {
    final res = await _api.dio.get("${ApiEndpoints.disenos}/$sessionId");
    return ((res.data["versiones"] as List<dynamic>?) ?? [])
        .map((d) => DisenoModel.fromJson(d as Map<String, dynamic>)).toList();
  }
}
