class EstadisticaSkuEntity {
  final String sku;
  final int vecesUsado;
  final int vecesReemplazado;
  final int vecesRechazado;
  final int vecesRecomendado;
  final String? ultimaFecha;

  const EstadisticaSkuEntity({
    required this.sku,
    required this.vecesUsado,
    required this.vecesReemplazado,
    required this.vecesRechazado,
    required this.vecesRecomendado,
    this.ultimaFecha,
  });

  int total() => vecesUsado + vecesReemplazado + vecesRechazado + vecesRecomendado;
}
