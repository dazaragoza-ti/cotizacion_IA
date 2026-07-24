import "dart:async";
import "package:flutter_bloc/flutter_bloc.dart";
import "rag_state.dart";
import "../../domain/usecases/buscar_rag_usecase.dart";
import "../../domain/usecases/sincronizar_rag_usecase.dart";
import "../../domain/usecases/get_sync_status_usecase.dart";
import "../../domain/entities/rag_resultado_entity.dart";

class RagCubit extends Cubit<RagState> {
  final BuscarRagUsecase _buscar;
  final SincronizarRagUsecase _sincronizar;
  final GetSyncStatusUsecase _getSyncStatus;
  Timer? _pollingSync;
  RagCubit(this._buscar, this._sincronizar, this._getSyncStatus) : super(RagInitial());

  Future<void> buscar(String query, {String? tipo}) async {
    if (query.trim().isEmpty) return;
    emit(RagBuscando());
    try {
      final resultados = await _buscar(query: query.trim(), topK: 8, tipo: tipo);
      emit(RagResultados(query: query.trim(), resultados: resultados));
    } catch (e) {
      emit(RagError(e.toString()));
    }
  }

  Future<void> sincronizar() async {
    final actual = state;
    final query = actual is RagResultados ? actual.query : "";
    final resultados = actual is RagResultados ? actual.resultados : const <RagResultadoEntity>[];
    emit(RagResultados(query: query, resultados: resultados, sincronizando: true, mensaje: "Sincronizando catálogo y correcciones..."));
    try {
      // El backend responde de inmediato y sigue sincronizando en segundo
      // plano (puede tardar mas de un minuto por el rate-limit de Voyage) --
      // por eso se consulta /rag/sync/status cada pocos segundos en vez de
      // asumir que ya termino apenas responde el POST.
      await _sincronizar();
      _iniciarPollingDeEstado(query, resultados);
    } catch (e) {
      emit(RagResultados(query: query, resultados: resultados, mensaje: "Error al sincronizar: $e"));
    }
  }

  void _iniciarPollingDeEstado(String query, List<RagResultadoEntity> resultados) {
    _pollingSync?.cancel();
    _pollingSync = Timer.periodic(const Duration(seconds: 3), (_) async {
      bool enProgreso;
      try {
        enProgreso = await _getSyncStatus();
      } catch (e) {
        // Un fallo puntual del polling no corta la animación; se avisa una vez.
        final actual = state;
        if (actual is RagResultados &&
            !(actual.mensaje?.contains("estado de sincronización") ?? false)) {
          emit(RagResultados(
            query: actual.query,
            resultados: actual.resultados,
            sincronizando: true,
            mensaje: "No se pudo consultar el estado de sincronización: $e",
          ));
        }
        return;
      }
      if (!enProgreso) {
        _pollingSync?.cancel();
        final actual = state;
        final q = actual is RagResultados ? actual.query : query;
        final r = actual is RagResultados ? actual.resultados : resultados;
        emit(RagResultados(query: q, resultados: r, mensaje: "Sincronización completada."));
      }
    });
  }

  @override
  Future<void> close() {
    _pollingSync?.cancel();
    return super.close();
  }
}
