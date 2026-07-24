import "package:flutter_bloc/flutter_bloc.dart";
import "historial_state.dart";
import "../../domain/usecases/get_historial_usecase.dart";
import "../../domain/usecases/get_versiones_usecase.dart";

class HistorialCubit extends Cubit<HistorialState> {
  final GetHistorialUsecase _getHistorial;
  final GetVersionesUsecase _getVersiones;
  HistorialCubit(this._getHistorial, this._getVersiones) : super(HistorialInitial());

  Future<void> loadHistorial() async {
    emit(HistorialLoading());
    try {
      emit(HistorialLoaded(disenos: await _getHistorial()));
    } catch (e) {
      emit(HistorialError(e.toString()));
    }
  }

  Future<void> selectSesion(String sessionId) async {
    if (state is! HistorialLoaded) return;
    final current = state as HistorialLoaded;
    emit(HistorialLoaded(
      disenos: current.disenos,
      selectedSessionId: sessionId,
      loadingVersiones: true,
    ));
    try {
      final versiones = await _getVersiones(sessionId);
      emit(HistorialLoaded(
        disenos: current.disenos,
        selectedSessionId: sessionId,
        versiones: versiones,
      ));
    } catch (e) {
      emit(HistorialLoaded(
        disenos: current.disenos,
        selectedSessionId: sessionId,
        errorVersiones: "No se pudieron cargar versiones: $e",
      ));
    }
  }
}
