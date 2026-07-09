import "package:flutter_bloc/flutter_bloc.dart";
import "correcciones_state.dart";
import "../../domain/usecases/list_correcciones_usecase.dart";
import "../../domain/usecases/delete_correccion_usecase.dart";

class CorreccionesCubit extends Cubit<CorreccionesState> {
  final ListCorreccionesUsecase _listCorrecciones;
  final DeleteCorreccionUsecase _deleteCorreccion;
  CorreccionesCubit(this._listCorrecciones, this._deleteCorreccion) : super(CorreccionesInitial());

  Future<void> loadCorrecciones() async {
    emit(CorreccionesLoading());
    try { emit(CorreccionesLoaded(correcciones: await _listCorrecciones())); }
    catch (e) { emit(CorreccionesError(e.toString())); }
  }

  Future<void> eliminarCorreccion(int correccionId) async {
    if (state is! CorreccionesLoaded) return;
    final current = state as CorreccionesLoaded;
    emit(CorreccionesLoaded(correcciones: current.correcciones, eliminandoId: correccionId));
    try {
      await _deleteCorreccion(correccionId);
      emit(CorreccionesLoaded(correcciones: current.correcciones.where((c) => c.id != correccionId).toList()));
    } catch (e) {
      emit(CorreccionesLoaded(correcciones: current.correcciones));
    }
  }
}
