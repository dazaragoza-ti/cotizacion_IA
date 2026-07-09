import '../entities/metrics_entity.dart';
import '../repositories/dashboard_repository.dart';

class GetMetricsUsecase {
  final DashboardRepository _repo;
  const GetMetricsUsecase(this._repo);
  Future<MetricsEntity> call() => _repo.getMetrics();
}
