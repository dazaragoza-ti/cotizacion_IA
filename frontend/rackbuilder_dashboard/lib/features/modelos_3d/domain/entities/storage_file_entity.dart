class StorageFileEntity {
  final String name;
  final String bucket;
  final String folder;
  final String path;
  final int size;
  final String type;
  final String url;
  final int? compressedSize;
  final double? compressionRatio;

  const StorageFileEntity({required this.name, required this.bucket, required this.folder,
      required this.path, required this.size, required this.type, required this.url,
      this.compressedSize, this.compressionRatio});

  bool get isOptimized => compressionRatio != null;
  String get formattedSize => fmt(size);
  String get formattedCompressed => compressedSize != null ? fmt(compressedSize!) : "—";

  static String fmt(int b) {
    if (b == 0) return "0 B";
    const s = ["B", "KB", "MB", "GB"];
    var val = b.toDouble(); var i = 0;
    while (val >= 1024 && i < s.length - 1) { val /= 1024; i++; }
    return "${val.toStringAsFixed(2)} ${s[i]}";
  }

  StorageFileEntity withResult({required int orig, required int comp}) {
    final ratio = orig > 0 ? double.parse(((orig - comp) / orig * 100).toStringAsFixed(1)) : 0.0;
    return StorageFileEntity(name: name, bucket: bucket, folder: folder, path: path,
        size: comp, type: type, url: url, compressedSize: comp, compressionRatio: ratio);
  }
}
