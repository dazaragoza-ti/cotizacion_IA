import "package:flutter_bloc/flutter_bloc.dart";
import "package:shared_preferences/shared_preferences.dart";
import "package:supabase_flutter/supabase_flutter.dart";
import "dashboard_state.dart";
import "../../domain/usecases/get_metrics_usecase.dart";
import "../../data/repositories/dashboard_repository_impl.dart";
import "../../../../core/network/api_client.dart";

class DashboardCubit extends Cubit<DashboardState> {
  final GetMetricsUsecase _getMetrics;
  // Referencia directa al repo para poder llamar setClient() y fetchSupabaseConfig()
  // sin recurrir al hack (as dynamic)._repo que falla en DDC (web)
  final DashboardRepositoryImpl _repo;
  final ApiClient _api;

  DashboardCubit(this._getMetrics, this._repo, this._api)
      : super(const DashboardInitial());

  Future<void> autoConnect() async {
    emit(const DashboardConnecting());

    final fastApi = await _probeFastApi();

    final prefs = await SharedPreferences.getInstance();
    var url = prefs.getString("sb_url") ?? "";
    var key = prefs.getString("sb_key") ?? "";
    if (url.isEmpty || key.isEmpty) {
      try {
        final config = await _repo.fetchSupabaseConfig();
        if (config != null) {
          url = config["url"]!;
          key = config["key"]!;
        }
      } catch (e) {
        emit(DashboardDisconnected(
          "No se pudo obtener config de Supabase: $e",
          fastApi: fastApi,
          supabase: ServiceHealth.fail(e.toString()),
        ));
        _scheduleReconnect(url, key);
        return;
      }
    }
    if (url.isEmpty || key.isEmpty) {
      emit(DashboardDisconnected(
        "No se encontraron credenciales de Supabase",
        fastApi: fastApi,
        supabase: ServiceHealth.fail("Sin credenciales"),
      ));
      return;
    }
    await connect(url, key, fastApiHint: fastApi);
  }

  Future<void> connect(String url, String key, {ServiceHealth? fastApiHint}) async {
    final fastApi = fastApiHint ?? await _probeFastApi();
    emit(DashboardConnecting(
      fastApi: fastApi,
      supabase: ServiceHealth.checkingNow,
    ));
    try {
      final client = SupabaseClient(url, key);
      _repo.setClient(client);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString("sb_url", url);
      await prefs.setString("sb_key", key);
      await refreshMetrics(fastApiHint: fastApi);
    } catch (e) {
      emit(DashboardDisconnected(
        e.toString(),
        fastApi: fastApi,
        supabase: ServiceHealth.fail(e.toString()),
      ));
      _scheduleReconnect(url, key);
    }
  }

  Future<void> refreshMetrics({ServiceHealth? fastApiHint}) async {
    final fastApi = fastApiHint ??
        (state.fastApi.checking ? await _probeFastApi() : state.fastApi);

    if (state is DashboardConnected) {
      emit(DashboardConnected(
        metrics: (state as DashboardConnected).metrics,
        loadingMetrics: true,
        fastApi: fastApi,
        supabase: state.supabase,
        warning: (state as DashboardConnected).warning,
      ));
    }

    try {
      final metrics = await _getMetrics();
      final warning = fastApi.ok
          ? null
          : (fastApi.error ?? "FastAPI no responde — algunos módulos pueden fallar.");
      emit(DashboardConnected(
        metrics: metrics,
        fastApi: fastApi,
        supabase: ServiceHealth.online,
        warning: warning,
      ));
    } catch (e) {
      if (state is DashboardConnected) {
        emit(DashboardConnected(
          metrics: (state as DashboardConnected).metrics,
          fastApi: fastApi,
          supabase: ServiceHealth.fail(e.toString()),
          warning: "Error al refrescar métricas: $e",
        ));
      } else {
        emit(DashboardDisconnected(
          e.toString(),
          fastApi: fastApi,
          supabase: ServiceHealth.fail(e.toString()),
        ));
      }
    }
  }

  /// Health check del backend (`GET /`) — independiente de Supabase.
  Future<ServiceHealth> _probeFastApi() async {
    try {
      final ok = await _api.checkHealth();
      return ok
          ? ServiceHealth.online
          : ServiceHealth.fail("Respuesta inesperada de FastAPI");
    } catch (e) {
      return ServiceHealth.fail(e.toString());
    }
  }

  void _scheduleReconnect(String url, String key) {
    if (url.isEmpty || key.isEmpty) return;
    Future.delayed(const Duration(seconds: 5), () async {
      if (state is! DashboardConnected) await connect(url, key);
    });
  }
}
