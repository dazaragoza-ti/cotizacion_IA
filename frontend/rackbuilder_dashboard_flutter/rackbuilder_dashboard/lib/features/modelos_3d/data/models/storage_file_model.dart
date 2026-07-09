import "../../domain/entities/storage_file_entity.dart";

class StorageFileModel extends StorageFileEntity {
  const StorageFileModel({required super.name, required super.bucket, required super.folder,
      required super.path, required super.size, required super.type, required super.url,
      super.compressedSize, super.compressionRatio});

  factory StorageFileModel.fromJson(Map<String, dynamic> json) {
    int size = 0;
    final rawSize = json["size"];
    if (rawSize != null) {
      size = (rawSize as num).toInt();
    } else {
      final meta = json["metadata"] as Map<String, dynamic>?;
      size = ((meta?["size"] ?? meta?["contentLength"] ?? 0) as num).toInt();
    }
    return StorageFileModel(name: json["name"] as String? ?? "", bucket: json["bucket"] as String? ?? "",
        folder: json["folder"] as String? ?? "", path: json["path"] as String? ?? "",
        size: size, type: json["type"] as String? ?? "", url: json["url"] as String? ?? "");
  }
}
