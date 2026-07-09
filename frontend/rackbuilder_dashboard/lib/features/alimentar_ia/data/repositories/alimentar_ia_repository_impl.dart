import "../../domain/entities/storage_entradas_entity.dart";
import "../../domain/repositories/alimentar_ia_repository.dart";
import "../datasources/alimentar_ia_remote_datasource.dart";

class AlimentarIaRepositoryImpl implements AlimentarIaRepository {
  final AlimentarIaRemoteDatasource _ds;
  const AlimentarIaRepositoryImpl(this._ds);

  @override
  Future<StorageEntradasEntity> listarEntradas({required String bucket, required String folder}) =>
      _ds.listarEntradas(bucket: bucket, folder: folder);

  @override
  Future<void> crearCarpeta({required String bucket, required String folderPath}) =>
      _ds.crearCarpeta(bucket: bucket, folderPath: folderPath);

  @override
  Future<String> subirArchivo({
    required String bucket,
    required String folder,
    required List<int> fileBytes,
    required String fileName,
  }) => _ds.subirArchivo(bucket: bucket, folder: folder, fileBytes: fileBytes, fileName: fileName);
}
