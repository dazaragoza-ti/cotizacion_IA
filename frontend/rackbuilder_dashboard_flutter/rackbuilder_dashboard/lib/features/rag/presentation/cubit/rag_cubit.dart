import "package:flutter_bloc/flutter_bloc.dart";
import "rag_state.dart";
import "../../domain/usecases/sincronizar_rag_usecase.dart";
import "../../domain/usecases/buscar_rag_usecase.dart";

class RagCubit extends Cubit<RagState> {
  final SincronizarRagUsecase _sincronizar;
  final BuscarRagUsecase _buscar;
  RagCubit(this._sincronizar, this._buscar) : super(const RagState());

  Future<void> sincronizar() async {
    emit(state.copyWith(syncing: true, syncMessage: "Reindexando catálogo y correcciones..."));
    try {
      await _sincronizar();
      emit(state.copyWith(syncing: false, syncSuccess: true, syncMessage: "Sincronización completada."));
    } catch (e) {
      emit(state.copyWith(syncing: false, syncSuccess: false, syncMessage: "Error: $e"));
    }
  }

  Future<void> buscar(String query, {int topK = 5, String? tipo}) async {
    if (query.trim().isEmpty) return;
    emit(state.copyWith(searching: true, searchError: ""));
    try {
      final resultados = await _buscar(query: query.trim(), topK: topK, tipo: tipo);
      emit(state.copyWith(searching: false, resultados: resultados));
    } catch (e) {
      emit(state.copyWith(searching: false, resultados: const [], searchError: e.toString()));
    }
  }
}
