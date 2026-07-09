import "package:flutter_bloc/flutter_bloc.dart";
import "estadisticas_state.dart";
import "../../domain/usecases/get_top_estadisticas_usecase.dart";
import "../../domain/usecases/get_estadistica_sku_usecase.dart";
import "../../domain/entities/estadistica_sku_entity.dart";
import "../../data/datasources/estadisticas_remote_datasource.dart" show camposEstadisticas;

class EstadisticasCubit extends Cubit<EstadisticasState> {
  final GetTopEstadisticasUsecase _getTop;
  final GetEstadisticaSkuUsecase _getSku;
  EstadisticasCubit(this._getTop, this._getSku) : super(EstadisticasInitial());

  Future<void> loadTop({String campo = "veces_reemplazado"}) async {
    emit(EstadisticasLoading());
    try {
      final top = await _getTop(campo: campo, limit: 10);
      emit(EstadisticasLoaded(campo: campo, top: top));
    } catch (e) {
      emit(EstadisticasError(e.toString()));
    }
  }

  Future<void> buscarSku(String sku) async {
    final actual = state;
    final campo = actual is EstadisticasLoaded ? actual.campo : camposEstadisticas.first;
    final top = actual is EstadisticasLoaded ? actual.top : const <EstadisticaSkuEntity>[];
    if (sku.trim().isEmpty) {
      emit(EstadisticasLoaded(campo: campo, top: top));
      return;
    }
    try {
      final resultado = await _getSku(sku.trim().toUpperCase());
      emit(EstadisticasLoaded(
        campo: campo, top: top, busqueda: resultado,
        mensajeBusqueda: resultado == null ? "Sin estadísticas registradas para ese SKU." : null,
      ));
    } catch (e) {
      emit(EstadisticasLoaded(campo: campo, top: top, mensajeBusqueda: "Error: $e"));
    }
  }
}
