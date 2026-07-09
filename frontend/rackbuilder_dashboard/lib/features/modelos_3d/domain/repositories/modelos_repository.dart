import "../entities/storage_file_entity.dart";

abstract class ModelosRepository {
  Future<List<StorageFileEntity>> listModelos();
  Future<Map<String, dynamic>> optimizeModelo(String bucket, String path);
}
