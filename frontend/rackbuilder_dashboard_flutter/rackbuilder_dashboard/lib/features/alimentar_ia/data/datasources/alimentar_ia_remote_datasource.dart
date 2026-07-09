import "package:dio/dio.dart";
import "../models/storage_entradas_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class AlimentarIaRemoteDatasource {
  Future<StorageEntradasModel> listarEntradas({required String bucket, required String folder});
  Future<void> crearCarpeta({required String bucket, required String folderPath});
  Future<String> subirArchivo({
    required String bucket,
    required String folder,
    required List<int> fileBytes,
    required String fileName,
  });
}

class AlimentarIaRemoteDatasourceImpl implements AlimentarIaRemoteDatasource {
  final ApiClient _api;
  const AlimentarIaRemoteDatasourceImpl(this._api);

  @override
  Future<StorageEntradasModel> listarEntradas({required String bucket, required String folder}) async {
    final res = await _api.dio.get(ApiEndpoints.storageEntradas, queryParameters: {
      "bucket": bucket,
      "folder": folder,
    });
    return StorageEntradasModel.fromJson(res.data as Map<String, dynamic>);
  }

  @override
  Future<void> crearCarpeta({required String bucket, required String folderPath}) async {
    final formData = FormData.fromMap({"bucket": bucket, "folder_path": folderPath});
    await _api.dio.post(ApiEndpoints.storageCarpeta, data: formData);
  }

  @override
  Future<String> subirArchivo({
    required String bucket,
    required String folder,
    required List<int> fileBytes,
    required String fileName,
  }) async {
    final formData = FormData.fromMap({
      "bucket": bucket,
      "folder": folder,
      "file": MultipartFile.fromBytes(fileBytes, filename: fileName),
    });
    final res = await _api.dio.post(ApiEndpoints.storageSubirArchivo, data: formData);
    return (res.data as Map<String, dynamic>)["url"] as String? ?? "";
  }
}
