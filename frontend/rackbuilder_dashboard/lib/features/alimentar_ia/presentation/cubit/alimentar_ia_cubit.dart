import "package:flutter_bloc/flutter_bloc.dart";
import "alimentar_ia_state.dart";
import "../../domain/entities/storage_bucket.dart";
import "../../domain/usecases/listar_entradas_usecase.dart";
import "../../domain/usecases/crear_carpeta_usecase.dart";
import "../../domain/usecases/subir_archivo_usecase.dart";

class AlimentarIaCubit extends Cubit<AlimentarIaState> {
  final ListarEntradasUsecase _listar;
  final CrearCarpetaUsecase _crearCarpeta;
  final SubirArchivoUsecase _subirArchivo;

  AlimentarIaCubit(this._listar, this._crearCarpeta, this._subirArchivo) : super(AlimentarIaInitial());

  Future<void> abrirExplorador({StorageBucket bucket = StorageBucket.cotizaciones}) =>
      _cargar(bucket: bucket, pathSegments: bucket.rootPath);

  Future<void> cambiarBucket(StorageBucket bucket) => _cargar(bucket: bucket, pathSegments: bucket.rootPath);

  Future<void> abrirCarpeta(String nombre) {
    final actual = state is AlimentarIaLoaded ? state as AlimentarIaLoaded : null;
    final bucket = actual?.bucket ?? StorageBucket.cotizaciones;
    final nuevaRuta = [...(actual?.pathSegments ?? <String>[]), nombre];
    return _cargar(bucket: bucket, pathSegments: nuevaRuta);
  }

  /// Navega a un segmento del breadcrumb. index == -1 vuelve a la raíz.
  Future<void> navegarA(int index) {
    final actual = state is AlimentarIaLoaded ? state as AlimentarIaLoaded : null;
    final bucket = actual?.bucket ?? StorageBucket.cotizaciones;
    final actuales = actual?.pathSegments ?? <String>[];
    final nuevaRuta = index < 0 ? <String>[] : actuales.sublist(0, index + 1);
    return _cargar(bucket: bucket, pathSegments: nuevaRuta);
  }

  Future<void> _cargar({required StorageBucket bucket, required List<String> pathSegments}) async {
    emit(AlimentarIaLoading());
    try {
      final entradas = await _listar(bucket: bucket.key, folder: pathSegments.join("/"));
      emit(AlimentarIaLoaded(
        bucket: bucket, pathSegments: pathSegments,
        carpetas: entradas.carpetas, archivos: entradas.archivos,
      ));
    } catch (e) {
      emit(AlimentarIaError(e.toString()));
    }
  }

  Future<void> crearCarpeta(String nombre) async {
    final actual = state is AlimentarIaLoaded ? state as AlimentarIaLoaded : null;
    if (actual == null || nombre.trim().isEmpty) return;

    emit(actual.copyWith(creandoCarpeta: true));
    final rutaNueva = [...actual.pathSegments, nombre.trim()].join("/");
    try {
      await _crearCarpeta(bucket: actual.bucket.key, folderPath: rutaNueva);
      final entradas = await _listar(bucket: actual.bucket.key, folder: actual.folderPath);
      emit(AlimentarIaLoaded(
        bucket: actual.bucket, pathSegments: actual.pathSegments,
        carpetas: entradas.carpetas, archivos: entradas.archivos,
        success: true, message: "Carpeta '${nombre.trim()}' creada.",
      ));
    } catch (e) {
      emit(actual.copyWith(message: "Error al crear carpeta: $e"));
    }
  }

  Future<void> subirArchivo({required List<int> bytes, required String fileName}) async {
    final actual = state is AlimentarIaLoaded ? state as AlimentarIaLoaded : null;
    if (actual == null) return;

    emit(actual.copyWith(uploading: true, message: "Subiendo..."));
    try {
      await _subirArchivo(
        bucket: actual.bucket.key, folder: actual.folderPath,
        fileBytes: bytes, fileName: fileName,
      );
      final entradas = await _listar(bucket: actual.bucket.key, folder: actual.folderPath);
      emit(AlimentarIaLoaded(
        bucket: actual.bucket, pathSegments: actual.pathSegments,
        carpetas: entradas.carpetas, archivos: entradas.archivos,
        success: true, message: "Archivo subido correctamente.",
      ));
    } catch (e) {
      emit(actual.copyWith(message: "Error al subir: $e"));
    }
  }
}
