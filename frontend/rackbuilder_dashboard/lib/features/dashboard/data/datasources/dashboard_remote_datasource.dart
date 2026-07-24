import "package:dio/dio.dart";
import "package:supabase_flutter/supabase_flutter.dart";
import "../models/metrics_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class DashboardRemoteDatasource {
  Future<MetricsModel> getMetrics(SupabaseClient supabase);
  Future<Map<String, String>?> fetchSupabaseConfig();
}

class DashboardRemoteDatasourceImpl implements DashboardRemoteDatasource {
  final ApiClient _api;
  const DashboardRemoteDatasourceImpl(this._api);

  @override
  Future<MetricsModel> getMetrics(SupabaseClient supabase) async {
    final res = await supabase.from("disenos_racks").select("input_tokens, output_tokens");
    return MetricsModel.fromRows(res as List<dynamic>);
  }

  @override
  Future<Map<String, String>?> fetchSupabaseConfig() async {
    try {
      final res = await _api.dio.get(ApiEndpoints.configSupabase);
      final url = res.data["url"] as String?;
      final key = res.data["key"] as String?;
      if (url != null && key != null && url.isNotEmpty && key.isNotEmpty) {
        return {"url": url, "key": key};
      }
      throw Exception("Respuesta de /config/supabase incompleta (url/key vacíos)");
    } on DioException catch (e) {
      final detail = e.error?.toString() ?? e.message ?? "Error de red";
      throw Exception("FastAPI no entregó config de Supabase: $detail");
    }
  }
}
