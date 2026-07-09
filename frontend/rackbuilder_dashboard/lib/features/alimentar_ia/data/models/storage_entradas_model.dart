import "../../domain/entities/storage_folder_entity.dart";
import "../../domain/entities/storage_file_entity.dart";
import "../../domain/entities/storage_entradas_entity.dart";

class StorageFolderModel extends StorageFolderEntity {
  const StorageFolderModel({required super.name, required super.path});

  factory StorageFolderModel.fromJson(Map<String, dynamic> j) => StorageFolderModel(
    name: j["name"] as String? ?? "",
    path: j["path"] as String? ?? "",
  );
}

class StorageFileModel extends StorageFileEntity {
  const StorageFileModel({
    required super.name,
    required super.path,
    required super.size,
    required super.type,
    required super.url,
  });

  factory StorageFileModel.fromJson(Map<String, dynamic> j) => StorageFileModel(
    name: j["name"] as String? ?? "",
    path: j["path"] as String? ?? "",
    size: (j["size"] as num?)?.toInt() ?? 0,
    type: j["type"] as String? ?? "archivo",
    url: j["url"] as String? ?? "",
  );
}

class StorageEntradasModel extends StorageEntradasEntity {
  const StorageEntradasModel({
    required super.bucket,
    required super.folder,
    required super.carpetas,
    required super.archivos,
  });

  factory StorageEntradasModel.fromJson(Map<String, dynamic> j) => StorageEntradasModel(
    bucket: j["bucket"] as String? ?? "",
    folder: j["folder"] as String? ?? "",
    carpetas: ((j["carpetas"] as List<dynamic>?) ?? [])
        .map((c) => StorageFolderModel.fromJson(c as Map<String, dynamic>)).toList(),
    archivos: ((j["archivos"] as List<dynamic>?) ?? [])
        .map((a) => StorageFileModel.fromJson(a as Map<String, dynamic>)).toList(),
  );
}
