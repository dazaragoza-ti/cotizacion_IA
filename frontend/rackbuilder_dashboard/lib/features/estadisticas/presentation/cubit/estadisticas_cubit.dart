import "package:flutter_bloc/flutter_bloc.dart";
import "estadisticas_state.dart";
import "../../domain/usecases/get_top_estadisticas_usecase.dart";
import "../../domain/usecases/get_estadistica_sku_usecase.dart";
import "../../domain/usecases/get_correcciones_usecase.dart";
import "../../domain/entities/estadistica_sku_entity.dart";
import "../../domain/entities/correccion_entity.dart";
import "../../data/datasources/estadisticas_remote_datasource.dart" show camposEstadisticas;

class EstadisticasCubit extends Cubit<EstadisticasState> {
  final GetTopEstadisticasUsecase _getTop;
  final GetEstadisticaSkuUsecase _getSku;
  final GetCorreccionesUsecase _getCorrecciones;
  EstadisticasCubit(this._getTop, this._getSku, this._getCorrecciones) : super(EstadisticasInitial());

  /// Carga el ranking y las correcciones aprendidas juntos -- es lo que se
  /// llama al abrir el modulo, para no dejar media pantalla en blanco.
  Future<void> cargarTodo({String campo = "veces_reemplazado"}) async {
    emit(EstadisticasLoading());
    try {
      final top = await _getTop(campo: campo, limit: 10);
      emit(EstadisticasLoaded(campo: campo, top: top, cargandoCorrecciones: true));
    } catch (e) {
      emit(EstadisticasError(e.toString()));
      return;
    }
    await _cargarCorrecciones();
  }

  Future<void> loadTop({String campo = "veces_reemplazado"}) async {
    emit(EstadisticasLoading());
    try {
      final top = await _getTop(campo: campo, limit: 10);
      emit(EstadisticasLoaded(campo: campo, top: top));
    } catch (e) {
      emit(EstadisticasError(e.toString()));
    }
  }

  Future<void> _cargarCorrecciones() async {
    final actual = state;
    if (actual is! EstadisticasLoaded) return;
    try {
      final correcciones = await _getCorrecciones();
      // Mas repetidas primero para que lo mas cerca de volverse regla
      // permanente salga arriba.
      correcciones.sort((a, b) => b.vecesRepetida.compareTo(a.vecesRepetida));
      emit((state as EstadisticasLoaded).copyWith(
        correcciones: correcciones,
        cargandoCorrecciones: false,
        clearWarning: true,
      ));
    } catch (e) {
      if (state is EstadisticasLoaded) {
        emit((state as EstadisticasLoaded).copyWith(
          cargandoCorrecciones: false,
          warning: "No se pudieron cargar correcciones: $e",
        ));
      }
    }
  }

  Future<void> buscarSku(String sku) async {
    final actual = state;
    final campo = actual is EstadisticasLoaded ? actual.campo : camposEstadisticas.first;
    final top = actual is EstadisticasLoaded ? actual.top : const <EstadisticaSkuEntity>[];
    final correcciones = actual is EstadisticasLoaded ? actual.correcciones : const <CorreccionEntity>[];
    if (sku.trim().isEmpty) {
      emit(EstadisticasLoaded(campo: campo, top: top, correcciones: correcciones));
      return;
    }
    try {
      final resultado = await _getSku(sku.trim().toUpperCase());
      emit(EstadisticasLoaded(
        campo: campo, top: top, busqueda: resultado, correcciones: correcciones,
        mensajeBusqueda: resultado == null ? "Sin estadísticas registradas para ese SKU." : null,
      ));
    } catch (e) {
      emit(EstadisticasLoaded(campo: campo, top: top, correcciones: correcciones, mensajeBusqueda: "Error: $e"));
    }
  }
}
