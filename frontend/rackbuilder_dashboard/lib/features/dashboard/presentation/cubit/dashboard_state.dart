import "package:equatable/equatable.dart";
import "../../domain/entities/metrics_entity.dart";

/// Estado de un servicio individual (FastAPI o Supabase).
class ServiceHealth extends Equatable {
  final bool ok;
  final bool checking;
  final String? error;

  const ServiceHealth({this.ok = false, this.checking = false, this.error});

  static const checkingNow = ServiceHealth(checking: true);
  static const offline = ServiceHealth();
  static const online = ServiceHealth(ok: true);

  factory ServiceHealth.fail(String message) =>
      ServiceHealth(ok: false, error: message);

  @override
  List<Object?> get props => [ok, checking, error];
}

abstract class DashboardState extends Equatable {
  final ServiceHealth fastApi;
  final ServiceHealth supabase;

  const DashboardState({
    this.fastApi = ServiceHealth.checkingNow,
    this.supabase = ServiceHealth.checkingNow,
  });

  /// Módulos que hablan con el backend vía Dio pueden operar si FastAPI responde.
  bool get backendOk => fastApi.ok;

  /// Métricas y Realtime requieren cliente Supabase activo.
  bool get supabaseOk => supabase.ok;

  @override
  List<Object?> get props => [fastApi, supabase];
}

class DashboardInitial extends DashboardState {
  const DashboardInitial();
}

class DashboardConnecting extends DashboardState {
  const DashboardConnecting({super.fastApi, super.supabase});
}

class DashboardConnected extends DashboardState {
  final MetricsEntity metrics;
  final bool loadingMetrics;
  final String? warning;

  const DashboardConnected({
    required this.metrics,
    this.loadingMetrics = false,
    this.warning,
    super.fastApi = ServiceHealth.online,
    super.supabase = ServiceHealth.online,
  });

  @override
  List<Object?> get props => [...super.props, metrics, loadingMetrics, warning];
}

class DashboardDisconnected extends DashboardState {
  final String message;

  const DashboardDisconnected(
    this.message, {
    super.fastApi = ServiceHealth.offline,
    super.supabase = ServiceHealth.offline,
  });

  @override
  List<Object?> get props => [...super.props, message];
}
