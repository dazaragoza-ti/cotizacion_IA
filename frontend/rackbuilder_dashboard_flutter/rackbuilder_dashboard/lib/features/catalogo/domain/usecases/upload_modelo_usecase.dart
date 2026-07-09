import "../repositories/catalogo_repository.dart";
class UploadModeloUsecase {
  final CatalogoRepository _repo;
  const UploadModeloUsecase(this._repo);
  Future<Map<String, dynamic>> call({
    required String codigoSku, required String nombre, required String tipo,
    required double pesoMaximo, required double longitud, required double altura,
    required double profundidad, required List<int> fileBytes, required String fileName,
    required bool comprimirDraco, required String encoderMethod,
  }) => _repo.uploadModelo(codigoSku: codigoSku, nombre: nombre, tipo: tipo,
      pesoMaximo: pesoMaximo, longitud: longitud, altura: altura, profundidad: profundidad,
      fileBytes: fileBytes, fileName: fileName, comprimirDraco: comprimirDraco, encoderMethod: encoderMethod);
}
