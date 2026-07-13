import "package:flutter_bloc/flutter_bloc.dart";
import "rag_state.dart";
import "../../domain/usecases/buscar_rag_usecase.dart";
import "../../domain/usecases/sincronizar_rag_usecase.dart";
import "../../domain/entities/rag_resultado_entity.dart";

class RagCubit extends Cubit<RagState> {
  final BuscarRagUsecase _buscar;
  final SincronizarRagUsecase _sincronizar;
  RagCubit(this._buscar, this._sincronizar) : super(RagInitial());

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
    emit(RagResultados(query: query, resultados: resultados, sincronizando: true, mensaje: "Iniciando sincronización..."));
    try {
      // El backend responde de inmediato y sigue sincronizando en segundo
      // plano (puede tardar más de un minuto por el rate-limit de Voyage) --
      // no hay que esperar a que termine para saber si arrancó bien.
      await _sincronizar();
      emit(RagResultados(query: query, resultados: resultados,
          mensaje: "Sincronización iniciada en segundo plano — puede tardar uno o dos minutos en verse reflejada en la búsqueda."));
    } catch (e) {
      emit(RagResultados(query: query, resultados: resultados, mensaje: "Error al sincronizar: $e"));
    }
  }
}
