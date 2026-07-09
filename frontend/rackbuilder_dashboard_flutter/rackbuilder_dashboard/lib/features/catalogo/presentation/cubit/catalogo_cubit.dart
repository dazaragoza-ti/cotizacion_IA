import "package:flutter_bloc/flutter_bloc.dart";
import "../../domain/entities/pieza_entity.dart";
import "catalogo_state.dart";
import "../../domain/usecases/get_catalogo_usecase.dart";
import "../../domain/usecases/upload_modelo_usecase.dart";
import "../../domain/usecases/delete_pieza_usecase.dart";

class CatalogoCubit extends Cubit<CatalogoState> {
  final GetCatalogoUsecase _get;
  final UploadModeloUsecase _upload;
  final DeletePiezaUsecase _delete;
  CatalogoCubit(this._get, this._upload, this._delete) : super(CatalogoInitial());

  Future<void> loadCatalogo() async {
    emit(CatalogoLoading());
    try { emit(CatalogoLoaded(piezas: await _get())); }
    catch (e) { emit(CatalogoError(e.toString())); }
  }

  Future<void> uploadModelo({
    required String codigoSku, required String nombre, required String tipo,
    required double pesoMaximo, required double longitud, required double altura,
    required double profundidad, required List<int> fileBytes, required String fileName,
    required bool comprimirDraco, required String encoderMethod,
  }) async {
    final current = state is CatalogoLoaded ? (state as CatalogoLoaded).piezas : <PiezaEntity>[];
    emit(CatalogoLoaded(piezas: current, uploading: true, message: "Procesando..."));
    try {
      await _upload(codigoSku: codigoSku, nombre: nombre, tipo: tipo,
          pesoMaximo: pesoMaximo, longitud: longitud, altura: altura, profundidad: profundidad,
          fileBytes: fileBytes, fileName: fileName, comprimirDraco: comprimirDraco, encoderMethod: encoderMethod);
      final updated = await _get();
      emit(CatalogoLoaded(piezas: updated, success: true, message: "Pieza registrada correctamente"));
    } catch (e) {
      emit(CatalogoLoaded(piezas: current, message: "Error: $e", success: false));
    }
  }

  Future<void> deletePieza(String sku) async {
    try {
      await _delete(sku);
      final updated = await _get();
      emit(CatalogoLoaded(piezas: updated, message: "Pieza eliminada"));
    } catch (e) {
      final current = state is CatalogoLoaded ? (state as CatalogoLoaded).piezas : <PiezaEntity>[];
      emit(CatalogoLoaded(piezas: current, message: "Error: $e"));
    }
  }
}
