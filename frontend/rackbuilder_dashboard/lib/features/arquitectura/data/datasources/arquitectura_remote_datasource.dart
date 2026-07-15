import "dart:async";
import "package:supabase_flutter/supabase_flutter.dart";
import "../../domain/error_sistema.dart";
import "../../domain/evento_pipeline.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class ArquitecturaRemoteDatasource {
  Future<List<ErrorSistema>> getErroresActivos();
  Future<void> resolverError(String id);
  Future<Map<String, dynamic>> getMetricas();

  /// Emite cada vez que cambia una fila en alguna de las tablas vigiladas
  /// (Supabase Realtime). El cubit reacciona re-consultando metricas/errores.
  Stream<void> watchCambios();

  /// true cuando el canal de Realtime quedo suscrito con exito, false si
  /// fallo (config no disponible, tabla sin publicar, etc.) -- en ese caso
  /// el modulo sigue funcionando con el polling de respaldo.
  Stream<bool> watchConexion();

  /// Cada paso de UNA solicitud puntual mientras avanza por el pipeline real
  /// (tabla eventos_pipeline) -- permite animar en el mapa por que nodo va
  /// pasando esa peticion en este instante, no solo contadores agregados.
  Stream<EventoPipeline> watchEventosPipeline();
}

class ArquitecturaRemoteDatasourceImpl implements ArquitecturaRemoteDatasource {
  final ApiClient _api;

  ArquitecturaRemoteDatasourceImpl(this._api);

  static const _tablasEnVivo = [
    "sistema_errores",
    "knowledge_edges",
    "knowledge_chunks",
    "reglas_armado",
    "disenos_racks",
  ];

  SupabaseClient? _realtimeClient;
  RealtimeChannel? _canal;
  StreamController<void>? _cambiosController;
  StreamController<bool>? _conexionController;
  StreamController<EventoPipeline>? _eventosController;

  @override
  Future<List<ErrorSistema>> getErroresActivos() async {
    final res = await _api.dio.get("/sistema/errores", queryParameters: {
      "limit": 20,
      "solo_activos": true,
    });
    return ((res.data["errores"] as List<dynamic>?) ?? [])
        .map((e) => ErrorSistema.fromJson(e as Map<String, dynamic>)).toList();
  }

  @override
  Future<void> resolverError(String id) async {
    await _api.dio.post("/sistema/errores/$id/resolver");
  }

  @override
  Future<Map<String, dynamic>> getMetricas() async {
    final res = await _api.dio.get("/sistema/metricas");
    return (res.data["metricas"] as Map<String, dynamic>?) ?? {};
  }

  @override
  Stream<void> watchCambios() {
    _asegurarConexion();
    return _cambiosController!.stream;
  }

  @override
  Stream<bool> watchConexion() {
    _asegurarConexion();
    return _conexionController!.stream;
  }

  @override
  Stream<EventoPipeline> watchEventosPipeline() {
    _asegurarConexion();
    return _eventosController!.stream;
  }

  void _asegurarConexion() {
    if (_cambiosController != null) return;

    final cambios = StreamController<void>.broadcast(onCancel: _cerrarConexion);
    final conexion = StreamController<bool>.broadcast(onCancel: _cerrarConexion);
    final eventos = StreamController<EventoPipeline>.broadcast(onCancel: _cerrarConexion);
    _cambiosController = cambios;
    _conexionController = conexion;
    _eventosController = eventos;
    _conectarRealtime(cambios, conexion, eventos);
  }

  void _cerrarConexion() {
    _canal?.unsubscribe();
    _realtimeClient?.dispose();
    _canal = null;
    _realtimeClient = null;
    _cambiosController = null;
    _conexionController = null;
    _eventosController = null;
  }

  Future<void> _conectarRealtime(
    StreamController<void> cambios,
    StreamController<bool> conexion,
    StreamController<EventoPipeline> eventos,
  ) async {
    try {
      final res = await _api.dio.get(ApiEndpoints.configSupabase);
      final url = res.data["url"] as String?;
      final key = res.data["key"] as String?;
      if (url == null || key == null || url.isEmpty || key.isEmpty) {
        if (!conexion.isClosed) conexion.add(false);
        return;
      }

      final client = SupabaseClient(url, key);
      _realtimeClient = client;
      var canal = client.channel("arquitectura-realtime");
      for (final tabla in _tablasEnVivo) {
        canal = canal.onPostgresChanges(
          event: PostgresChangeEvent.all,
          schema: "public",
          table: tabla,
          callback: (payload) {
            if (!cambios.isClosed) cambios.add(null);
          },
        );
      }
      canal = canal.onPostgresChanges(
        event: PostgresChangeEvent.insert,
        schema: "public",
        table: "eventos_pipeline",
        callback: (payload) {
          if (eventos.isClosed) return;
          try {
            eventos.add(EventoPipeline.fromJson(payload.newRecord));
          } catch (_) {}
        },
      );
      _canal = canal;
      canal.subscribe((status, error) {
        if (conexion.isClosed) return;
        conexion.add(status == RealtimeSubscribeStatus.subscribed);
      });
    } catch (_) {
      // Silencioso: si Realtime no esta disponible el modulo sigue
      // funcionando por polling (ver ArquitecturaCubit.iniciarPolling).
      if (!conexion.isClosed) conexion.add(false);
    }
  }
}
