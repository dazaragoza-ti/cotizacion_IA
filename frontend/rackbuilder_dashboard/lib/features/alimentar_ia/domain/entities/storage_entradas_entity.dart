import "storage_folder_entity.dart";
import "storage_file_entity.dart";

class StorageEntradasEntity {
  final String bucket;
  final String folder;
  final List<StorageFolderEntity> carpetas;
  final List<StorageFileEntity> archivos;

  const StorageEntradasEntity({
    required this.bucket,
    required this.folder,
    required this.carpetas,
    required this.archivos,
  });
}
