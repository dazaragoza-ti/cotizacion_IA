import "dart:async";
import "package:flutter_bloc/flutter_bloc.dart";
import "arquitectura_state.dart";
import "../../data/datasources/arquitectura_remote_datasource.dart";
import "../../domain/evento_pipeline.dart";

class ArquitecturaCubit extends Cubit<ArquitecturaState> {
  final ArquitecturaRemoteDatasource _ds;
  Timer? _timer;
  Timer? _debounce;
  StreamSubscription<void>? _cambiosSub;
  StreamSubscription<bool>? _conexionSub;
  StreamSubscription<EventoPipeline>? _eventosSub;
  final Map<String, Timer> _vencimientos = {};
  ArquitecturaCubit(this._ds) : super(const ArquitecturaState());

  Future<void> cargarErrores() async {
    try {
      final errores = await _ds.getErroresActivos();
      emit(state.copyWith(errores: errores, cargando: false, clearMensaje: true));
    } catch (e) {
      emit(state.copyWith(
        cargando: false,
        mensajeError: "No se pudieron cargar errores del sistema: $e",
      ));
    }
  }

  Future<void> cargarMetricas() async {
    try {
      final metricas = await _ds.getMetricas();
      emit(state.copyWith(metricas: metricas, clearMensaje: true));
    } catch (e) {
      emit(state.copyWith(
        mensajeError: "No se pudieron cargar métricas de arquitectura: $e",
      ));
    }
  }

  /// Refresca al abrir la pantalla, cada 30s como respaldo, y al instante
  /// cuando Supabase Realtime avisa un cambio en las tablas vigiladas.
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

    _eventosSub?.cancel();
    _eventosSub = _ds.watchEventosPipeline().listen(_onEventoPipeline);
  }

  void _onEventoPipeline(EventoPipeline evento) {
    final nodoId = evento.componente;
    final actuales = Map<String, String>.from(state.pasosEnCurso)..[nodoId] = evento.paso;
    emit(state.copyWith(pasosEnCurso: actuales));

    final espera = evento.estado == "en_progreso"
        ? const Duration(seconds: 20)
        : const Duration(milliseconds: 700);
    _vencimientos[nodoId]?.cancel();
    _vencimientos[nodoId] = Timer(espera, () {
      final limpio = Map<String, String>.from(state.pasosEnCurso)..remove(nodoId);
      emit(state.copyWith(pasosEnCurso: limpio));
    });
  }

  Future<void> resolverError(String id) async {
    try {
      await _ds.resolverError(id);
      await cargarErrores();
    } catch (e) {
      emit(state.copyWith(mensajeError: "No se pudo resolver el error: $e"));
    }
  }

  void limpiarMensaje() {
    if (state.mensajeError != null) emit(state.copyWith(clearMensaje: true));
  }

  @override
  Future<void> close() {
    _timer?.cancel();
    _debounce?.cancel();
    _cambiosSub?.cancel();
    _conexionSub?.cancel();
    _eventosSub?.cancel();
    for (final t in _vencimientos.values) {
      t.cancel();
    }
    return super.close();
  }
}
