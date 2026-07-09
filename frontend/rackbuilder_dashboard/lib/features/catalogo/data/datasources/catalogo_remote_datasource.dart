import "package:dio/dio.dart";
import "../models/pieza_model.dart";
import "../../../../core/network/api_client.dart";
import "../../../../core/constants/app_constants.dart";

abstract class CatalogoRemoteDatasource {
  Future<List<PiezaModel>> getPiezas();
  Future<Map<String, dynamic>> uploadModelo({
    required String codigoSku, required String nombre, required String tipo,
    required double pesoMaximo, required double longitud, required double altura,
    required double profundidad, required List<int> fileBytes, required String fileName,
    required bool comprimirDraco, required String encoderMethod,
  });
  Future<void> deletePieza(String codigoSku);
}

class CatalogoRemoteDatasourceImpl implements CatalogoRemoteDatasource {
  final ApiClient _api;
  const CatalogoRemoteDatasourceImpl(this._api);

  @override
  Future<List<PiezaModel>> getPiezas() async {
    final res = await _api.dio.get(ApiEndpoints.catalogoPiezas);
    return ((res.data["piezas"] as List<dynamic>?) ?? [])
        .map((p) => PiezaModel.fromJson(p as Map<String, dynamic>)).toList();
  }

  @override
  Future<Map<String, dynamic>> uploadModelo({
    required String codigoSku, required String nombre, required String tipo,
    required double pesoMaximo, required double longitud, required double altura,
    required double profundidad, required List<int> fileBytes, required String fileName,
    required bool comprimirDraco, required String encoderMethod,
  }) async {
    final formData = FormData.fromMap({
      "codigo_sku": codigoSku, "nombre": nombre, "tipo": tipo,
      "peso_maximo_soportado_kg": pesoMaximo.toString(),
      "longitud_metros": longitud.toString(), "altura_metros": altura.toString(),
      "profundidad_metros": profundidad.toString(),
      "comprimir_draco": comprimirDraco.toString(), "encoder_method": encoderMethod,
      "file": MultipartFile.fromBytes(fileBytes, filename: fileName),
    });
    final res = await _api.dio.post(ApiEndpoints.catalogoUpload, data: formData);
    return res.data as Map<String, dynamic>;
  }

  @override
  Future<void> deletePieza(String codigoSku) async {
    await _api.dio.delete("${ApiEndpoints.catalogoPiezas}/$codigoSku");
  }
}
