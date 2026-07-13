import "dart:async";
import "package:flutter_bloc/flutter_bloc.dart";
import "arquitectura_state.dart";
import "../../data/datasources/arquitectura_remote_datasource.dart";

class ArquitecturaCubit extends Cubit<ArquitecturaState> {
  final ArquitecturaRemoteDatasource _ds;
  Timer? _timer;
  Timer? _debounce;
  StreamSubscription<void>? _cambiosSub;
  StreamSubscription<bool>? _conexionSub;
  ArquitecturaCubit(this._ds) : super(const ArquitecturaState());

  Future<void> cargarErrores() async {
    try {
      final errores = await _ds.getErroresActivos();
      emit(state.copyWith(errores: errores, cargando: false));
    } catch (_) {
      // Silencioso: si el propio endpoint de monitoreo falla, no queremos que
      // el modulo de arquitectura (que es estatico) se rompa por eso.
      emit(state.copyWith(cargando: false));
    }
  }

  Future<void> cargarMetricas() async {
    try {
      final metricas = await _ds.getMetricas();
      emit(state.copyWith(metricas: metricas));
    } catch (_) {
      // Silencioso, mismo criterio que cargarErrores: el mapa estatico no
      // debe romperse si /sistema/metricas falla.
    }
  }

  /// Refresca al abrir la pantalla, cada 30s como respaldo, y al instante
  /// cuando Supabase Realtime avisa un cambio en las tablas vigiladas
  /// (sistema_errores, knowledge_edges, knowledge_chunks, reglas_armado,
  /// disenos_racks). El polling de 30s se conserva como red de seguridad
  /// por si Realtime no esta disponible (falta publicar la tabla, red, etc).
  void iniciarPolling() {
    cargarErrores();
    cargarMetricas();
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) {
      cargarErrores();
      cargarMetricas();
    });

    _cambiosSub?.cancel();
    _cambiosSub = _ds.watchCambios().listen((_) {
      // Debounce: una sincronizacion de RAG puede insertar decenas de
      // knowledge_chunks en rafaga -- se espera a que se calme antes de
      // re-consultar, para no martillar el backend.
      _debounce?.cancel();
      _debounce = Timer(const Duration(milliseconds: 800), () {
        cargarErrores();
        cargarMetricas();
      });
    });

    _conexionSub?.cancel();
    _conexionSub = _ds.watchConexion().listen((conectado) {
      emit(state.copyWith(enVivoConectado: conectado));
    });
  }

  Future<void> resolverError(String id) async {
    try {
      await _ds.resolverError(id);
      await cargarErrores();
    } catch (_) {}
  }

  @override
  Future<void> close() {
    _timer?.cancel();
    _debounce?.cancel();
    _cambiosSub?.cancel();
    _conexionSub?.cancel();
    return super.close();
  }
}
