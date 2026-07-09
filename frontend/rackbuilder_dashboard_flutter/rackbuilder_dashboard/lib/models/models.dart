class DashboardMetrics {
  final int proyectos;
  final int inputTokens;
  final int outputTokens;
  final int totalTokens;
  final double avgTokensPerProject;
  final double estimatedCost;

  const DashboardMetrics({
    required this.proyectos,
    required this.inputTokens,
    required this.outputTokens,
    required this.totalTokens,
    required this.avgTokensPerProject,
    required this.estimatedCost,
  });

  factory DashboardMetrics.empty() => const DashboardMetrics(
        proyectos: 0,
        inputTokens: 0,
        outputTokens: 0,
        totalTokens: 0,
        avgTokensPerProject: 0,
        estimatedCost: 0,
      );
}

class StorageFileItem {
  final String name;
  final String bucket;
  final String folder;
  final String path;
  final int size;
  final String type;
  final String url;
  // Estos valores son null hasta que el modelo se haya optimizado con Draco.
  // El backend devuelve los valores reales tras la optimización.
  final int? compressedSize;
  final double? compressionRatio;

  const StorageFileItem({
    required this.name,
    required this.bucket,
    required this.folder,
    required this.path,
    required this.size,
    required this.type,
    required this.url,
    this.compressedSize,
    this.compressionRatio,
  });

  factory StorageFileItem.fromJson(Map<String, dynamic> json) {
    // El tamaño puede venir en size directo o anidado en metadata
    int size = 0;
    final rawSize = json['size'];
    if (rawSize != null) {
      size = (rawSize as num).toInt();
    } else {
      final meta = json['metadata'] as Map<String, dynamic>?;
      size = ((meta?['size'] ?? meta?['contentLength'] ?? 0) as num).toInt();
    }
    return StorageFileItem(
      name: json['name'] as String? ?? '',
      bucket: json['bucket'] as String? ?? '',
      folder: json['folder'] as String? ?? '',
      path: json['path'] as String? ?? '',
      size: size,
      type: json['type'] as String? ?? '',
      url: json['url'] as String? ?? '',
      // Sin valores de compresión hasta que se optimice
    );
  }

  /// Crea una copia con los resultados reales de la optimización Draco
  StorageFileItem withOptimizationResult({required int originalSize, required int compressedSizeResult}) {
    final ratio = originalSize > 0
        ? double.parse(((originalSize - compressedSizeResult) / originalSize * 100).toStringAsFixed(1))
        : 0.0;
    return StorageFileItem(
      name: name, bucket: bucket, folder: folder, path: path,
      size: compressedSizeResult,   // el archivo en storage ya fue reemplazado por el comprimido
      type: type, url: url,
      compressedSize: compressedSizeResult,
      compressionRatio: ratio,
    );
  }

  bool get isOptimized => compressionRatio != null;

  String get formattedSize => _formatBytes(size);
  String get formattedCompressed => compressedSize != null ? _formatBytes(compressedSize!) : '—';

  static String _formatBytes(int bytes) {  // público via StorageFileItem._formatBytes
    if (bytes == 0) return '0 B';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    var val = bytes.toDouble();
    var i = 0;
    while (val >= 1024 && i < sizes.length - 1) { val /= 1024; i++; }
    return '${val.toStringAsFixed(2)} ${sizes[i]}';
  }
}
