import '../entities/metrics_entity.dart';

abstract class DashboardRepository {
  Future<MetricsEntity> getMetrics();
  Future<Map<String, String>?> fetchSupabaseConfig();
}
