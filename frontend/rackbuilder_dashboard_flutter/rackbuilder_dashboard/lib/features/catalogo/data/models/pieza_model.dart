import "../../domain/entities/pieza_entity.dart";
class PiezaModel extends PiezaEntity {
  const PiezaModel({required super.codigoSku, required super.nombre, required super.tipo,
      required super.pesoMaximoKg, required super.longitudMetros, required super.alturaMetros,
      required super.profundidadMetros, super.urlModeloGlb});

  factory PiezaModel.fromJson(Map<String, dynamic> j) => PiezaModel(
    codigoSku: j["codigo_sku"] as String? ?? "",
    nombre: j["nombre"] as String? ?? "",
    tipo: j["tipo"] as String? ?? "",
    pesoMaximoKg: (j["peso_maximo_soportado_kg"] as num?)?.toDouble() ?? 0,
    longitudMetros: (j["longitud_metros"] as num?)?.toDouble() ?? 0,
    alturaMetros: (j["altura_metros"] as num?)?.toDouble() ?? 0,
    profundidadMetros: (j["profundidad_metros"] as num?)?.toDouble() ?? 0,
    urlModeloGlb: j["url_modelo_glb"] as String?,
  );
}
