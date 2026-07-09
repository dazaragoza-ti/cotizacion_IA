import "../entities/pieza_entity.dart";

abstract class CatalogoRepository {
  Future<List<PiezaEntity>> getPiezas();
  Future<Map<String, dynamic>> uploadModelo({
    required String codigoSku, required String nombre, required String tipo,
    required double pesoMaximo, required double longitud, required double altura,
    required double profundidad, required List<int> fileBytes, required String fileName,
    required bool comprimirDraco, required String encoderMethod,
  });
  Future<void> deletePieza(String codigoSku);
}
