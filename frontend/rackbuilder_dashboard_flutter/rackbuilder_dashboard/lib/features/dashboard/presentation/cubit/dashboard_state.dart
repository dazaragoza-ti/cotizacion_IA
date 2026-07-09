import "package:equatable/equatable.dart";
import "../../domain/entities/metrics_entity.dart";

abstract class DashboardState extends Equatable {
  @override List<Object?> get props => [];
}
class DashboardInitial    extends DashboardState {}
class DashboardConnecting extends DashboardState {}
class DashboardConnected  extends DashboardState {
  final MetricsEntity metrics;
  final bool loadingMetrics;
  DashboardConnected({required this.metrics, this.loadingMetrics = false});
  @override List<Object?> get props => [metrics, loadingMetrics];
}
class DashboardDisconnected extends DashboardState {
  final String message;
  DashboardDisconnected(this.message);
  @override List<Object?> get props => [message];
}
