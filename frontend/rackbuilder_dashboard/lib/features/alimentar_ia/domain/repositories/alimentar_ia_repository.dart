import "../entities/storage_entradas_entity.dart";

abstract class AlimentarIaRepository {
  Future<StorageEntradasEntity> listarEntradas({required String bucket, required String folder});
  Future<void> crearCarpeta({required String bucket, required String folderPath});
  Future<String> subirArchivo({
    required String bucket,
    required String folder,
    required List<int> fileBytes,
    required String fileName,
  });
}
