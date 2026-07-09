import "package:flutter_bloc/flutter_bloc.dart";
import "package:shared_preferences/shared_preferences.dart";
import "package:supabase_flutter/supabase_flutter.dart";
import "dashboard_state.dart";
import "../../domain/usecases/get_metrics_usecase.dart";
import "../../data/repositories/dashboard_repository_impl.dart";
import "../../data/datasources/dashboard_remote_datasource.dart";

class DashboardCubit extends Cubit<DashboardState> {
  final GetMetricsUsecase _getMetrics;
  // Referencia directa al repo para poder llamar setClient() y fetchSupabaseConfig()
  // sin recurrir al hack (as dynamic)._repo que falla en DDC (web)
  final DashboardRepositoryImpl _repo;

  DashboardCubit(this._getMetrics, this._repo) : super(DashboardInitial());

  Future<void> autoConnect() async {
    emit(DashboardConnecting());
    final prefs = await SharedPreferences.getInstance();
    var url = prefs.getString("sb_url") ?? "";
    var key = prefs.getString("sb_key") ?? "";
    if (url.isEmpty || key.isEmpty) {
      final config = await _repo.fetchSupabaseConfig();
      if (config != null) { url = config["url"]!; key = config["key"]!; }
    }
    if (url.isEmpty || key.isEmpty) {
      emit(DashboardDisconnected("No se encontraron credenciales de Supabase"));
      return;
    }
    await connect(url, key);
  }

  Future<void> connect(String url, String key) async {
    emit(DashboardConnecting());
    try {
      final client = SupabaseClient(url, key);
      _repo.setClient(client);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString("sb_url", url);
      await prefs.setString("sb_key", key);
      await refreshMetrics();
    } catch (e) {
      emit(DashboardDisconnected(e.toString()));
      _scheduleReconnect(url, key);
    }
  }

  Future<void> refreshMetrics() async {
    if (state is DashboardConnected) {
      emit(DashboardConnected(
          metrics: (state as DashboardConnected).metrics, loadingMetrics: true));
    }
    try {
      final metrics = await _getMetrics();
      emit(DashboardConnected(metrics: metrics));
    } catch (e) {
      if (state is! DashboardConnected) emit(DashboardDisconnected(e.toString()));
    }
  }

  void _scheduleReconnect(String url, String key) {
    Future.delayed(const Duration(seconds: 5), () async {
      if (state is! DashboardConnected) await connect(url, key);
    });
  }
}
