import "package:dio/dio.dart";
import "../models/storage_file_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class ModelosRemoteDatasource {
  Future<List<StorageFileModel>> listModelos();
  Future<Map<String, dynamic>> optimizeModelo(String bucket, String path);
}

class ModelosRemoteDatasourceImpl implements ModelosRemoteDatasource {
  final ApiClient _api;
  const ModelosRemoteDatasourceImpl(this._api);

  @override
  Future<List<StorageFileModel>> listModelos() async {
    final errors = <Object>[];
    final futures = await Future.wait([
      _fetchFiles(AppConstants.bucketModelos, AppConstants.folderModelos3D)
          .catchError((Object e) {
        errors.add(e);
        return <StorageFileModel>[];
      }),
      _fetchFiles(AppConstants.bucketModelos, "")
          .catchError((Object e) {
        errors.add(e);
        return <StorageFileModel>[];
      }),
    ]);
    final unique = <String, StorageFileModel>{};
    for (final list in futures) {
      for (final f in list) {
        unique[f.path] = f;
      }
    }
    final result = unique.values
        .where((f) =>
            f.name.toLowerCase().endsWith(".glb") ||
            f.name.toLowerCase().endsWith(".gltf"))
        .toList()
      ..sort((a, b) => a.name.compareTo(b.name));

    // Si no hay nada y al menos una carpeta falló, no devolver [] silencioso.
    if (result.isEmpty && errors.isNotEmpty) {
      throw errors.first;
    }
    return result;
  }

  Future<List<StorageFileModel>> _fetchFiles(String bucket, String folder) async {
    try {
      final res = await _api.dio.get(ApiEndpoints.storageFiles,
          queryParameters: {"bucket": bucket, "folder": folder});
      final files = (res.data["files"] as List<dynamic>? ?? []);
      return files
          .map((f) => StorageFileModel.fromJson(f as Map<String, dynamic>))
          .toList();
    } on DioException catch (e) {
      final detail = e.error?.toString() ?? e.message ?? "Error de red";
      throw Exception("No se pudieron listar modelos ($bucket/$folder): $detail");
    }
  }

  @override
  Future<Map<String, dynamic>> optimizeModelo(String bucket, String path) async {
    final res = await _api.dio.post(ApiEndpoints.storageOptimize,
        data: FormData.fromMap({"bucket": bucket, "path": path}));
    return res.data as Map<String, dynamic>;
  }
}
