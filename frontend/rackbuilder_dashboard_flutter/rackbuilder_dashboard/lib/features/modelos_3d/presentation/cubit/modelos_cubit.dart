import "package:flutter_bloc/flutter_bloc.dart";
import "modelos_state.dart";
import "../../domain/usecases/list_modelos_usecase.dart";
import "../../domain/usecases/optimize_modelo_usecase.dart";
import "../../domain/entities/storage_file_entity.dart";

class ModelosCubit extends Cubit<ModelosState> {
  final ListModelosUsecase _list;
  final OptimizeModeloUsecase _optimize;
  ModelosCubit(this._list, this._optimize) : super(ModelosInitial());

  Future<void> loadModelos() async {
    emit(ModelosLoading());
    try {
      final modelos = await _list();
      emit(ModelosLoaded(modelos: modelos));
    } catch (e) { emit(ModelosError(e.toString())); }
  }

  Future<void> optimizeModelo(StorageFileEntity model) async {
    if (state is! ModelosLoaded) return;
    final current = state as ModelosLoaded;
    emit(ModelosLoaded(modelos: current.modelos, optimizingPath: model.path, message: "Optimizando ${model.name}..."));
    try {
      final result = await _optimize(model.bucket, model.path);
      final orig = (result["original_size"] as num).toInt();
      final comp = (result["compressed_size"] as num).toInt();
      final pct  = orig > 0 ? ((orig - comp) / orig * 100).toStringAsFixed(1) : "0";
      final updated = current.modelos.map((m) => m.path == model.path
          ? m.withResult(orig: orig, comp: comp) : m).toList();
      emit(ModelosLoaded(modelos: updated,
          message: "${model.name}: ${StorageFileEntity.fmt(orig)} → ${StorageFileEntity.fmt(comp)} ($pct% reducción)"));
    } catch (e) {
      emit(ModelosLoaded(modelos: current.modelos, message: "Error: $e"));
    }
  }
}
