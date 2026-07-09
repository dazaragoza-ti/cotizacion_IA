class StorageFileEntity {
  final String name;
  final String path;
  final int size;
  final String type;
  final String url;

  const StorageFileEntity({
    required this.name,
    required this.path,
    required this.size,
    required this.type,
    required this.url,
  });

  String get sizeLabel {
    if (size <= 0) return "—";
    if (size < 1024) return "$size B";
    if (size < 1024 * 1024) return "${(size / 1024).toStringAsFixed(1)} KB";
    return "${(size / (1024 * 1024)).toStringAsFixed(1)} MB";
  }
}
