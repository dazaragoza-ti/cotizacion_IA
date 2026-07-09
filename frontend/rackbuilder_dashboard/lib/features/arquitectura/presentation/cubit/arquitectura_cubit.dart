import "dart:async";
import "package:flutter_bloc/flutter_bloc.dart";
import "arquitectura_state.dart";
import "../../data/datasources/arquitectura_remote_datasource.dart";

class ArquitecturaCubit extends Cubit<ArquitecturaState> {
  final ArquitecturaRemoteDatasource _ds;
  Timer? _timer;
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

  /// Refresca al abrir la pantalla y cada 30s mientras siga montada.
  void iniciarPolling() {
    cargarErrores();
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => cargarErrores());
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
    return super.close();
  }
}
