import "../../domain/entities/storage_file_entity.dart";
import "../../domain/repositories/modelos_repository.dart";
import "../datasources/modelos_remote_datasource.dart";

class ModelosRepositoryImpl implements ModelosRepository {
  final ModelosRemoteDatasource _ds;
  const ModelosRepositoryImpl(this._ds);

  @override Future<List<StorageFileEntity>> listModelos() => _ds.listModelos();
  @override Future<Map<String, dynamic>> optimizeModelo(String bucket, String path) =>
      _ds.optimizeModelo(bucket, path);
}
