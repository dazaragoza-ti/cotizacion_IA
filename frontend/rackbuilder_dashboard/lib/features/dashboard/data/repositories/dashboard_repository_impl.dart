import "package:supabase_flutter/supabase_flutter.dart";
import "../../domain/entities/metrics_entity.dart";
import "../../domain/repositories/dashboard_repository.dart";
import "../datasources/dashboard_remote_datasource.dart";

class DashboardRepositoryImpl implements DashboardRepository {
  final DashboardRemoteDatasource _ds;
  SupabaseClient? _supabase;
  DashboardRepositoryImpl(this._ds);
  void setClient(SupabaseClient client) => _supabase = client;

  @override
  Future<MetricsEntity> getMetrics() async {
    if (_supabase == null) throw Exception("Sin conexion a Supabase");
    return _ds.getMetrics(_supabase!);
  }

  @override
  Future<Map<String, String>?> fetchSupabaseConfig() => _ds.fetchSupabaseConfig();
}
