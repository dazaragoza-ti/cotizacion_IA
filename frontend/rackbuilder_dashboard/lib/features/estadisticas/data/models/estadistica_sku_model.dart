import "../../domain/entities/estadistica_sku_entity.dart";

class EstadisticaSkuModel extends EstadisticaSkuEntity {
  const EstadisticaSkuModel({
    required super.sku,
    required super.vecesUsado,
    required super.vecesReemplazado,
    required super.vecesRechazado,
    required super.vecesRecomendado,
    super.ultimaFecha,
  });

  factory EstadisticaSkuModel.fromJson(Map<String, dynamic> j) => EstadisticaSkuModel(
    sku: j["sku"] as String? ?? "",
    vecesUsado: (j["veces_usado"] as num?)?.toInt() ?? 0,
    vecesReemplazado: (j["veces_reemplazado"] as num?)?.toInt() ?? 0,
    vecesRechazado: (j["veces_rechazado"] as num?)?.toInt() ?? 0,
    vecesRecomendado: (j["veces_recomendado"] as num?)?.toInt() ?? 0,
    ultimaFecha: j["ultima_fecha"] as String?,
  );
}
