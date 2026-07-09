import "../../domain/entities/pieza_entity.dart";
import "../../domain/repositories/catalogo_repository.dart";
import "../datasources/catalogo_remote_datasource.dart";

class CatalogoRepositoryImpl implements CatalogoRepository {
  final CatalogoRemoteDatasource _ds;
  const CatalogoRepositoryImpl(this._ds);

  @override Future<List<PiezaEntity>> getPiezas() => _ds.getPiezas();
  @override Future<void> deletePieza(String sku) => _ds.deletePieza(sku);
  @override Future<Map<String, dynamic>> uploadModelo({
    required String codigoSku, required String nombre, required String tipo,
    required double pesoMaximo, required double longitud, required double altura,
    required double profundidad, required List<int> fileBytes, required String fileName,
    required bool comprimirDraco, required String encoderMethod,
  }) => _ds.uploadModelo(codigoSku: codigoSku, nombre: nombre, tipo: tipo,
      pesoMaximo: pesoMaximo, longitud: longitud, altura: altura, profundidad: profundidad,
      fileBytes: fileBytes, fileName: fileName, comprimirDraco: comprimirDraco, encoderMethod: encoderMethod);
}
